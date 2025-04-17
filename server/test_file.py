import json
import datetime
import logging
import re
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import time

import httpx
import jmespath
import requests

from utils.log_util import logger

{
    "4 0 ": "productCode",
    " 6 0 ": "itemGroup",
    " 7 0 ": "itemName",
    " 8 0 ": "brand",
    " 9 0 ": "category",
    " 10 0 ": "subCategory",
    " 11 0 ": "itemSize",
    " 12 0 ": "itemUnit",
    " 13 0 ": "itemOp",
    " 17 0 ": "statusCode",
    " 18 0 ": "returnIndicator",
    " 19 0 ": "supplierCode",
    " 23 0 ": "price",
    " 25 0 ": "priceSide",
    " 32 0 ": "promoStartDate",
    " 33 0 ": "promoEndDate",
    " 43 0 ": "stockOnHand",
    " 68 0 ": "rpType",
    " 69 0 ": "sugarGrade",
    " 70 0 ": "planogramInfo",
    " 72 0 ": "shortDescription",
    " 73 0 ": "supplySource",
    " 74 0 ": "supplySourceValue",
    " 75 0 ": "promoDescription",
    " 121 0 ": "itemIpf"
}

{
    "4 0 ": "productCode",
    " 7 0 ": "itemName",
    " 8 0 ": "brand",
    " 9 0 ": "category",
    " 10 0 ": "subCategory",
    " 11 0 ": "itemSize",
    " 12 0 ": "itemUnit",
    " 13 0 ": "itemOp",
    " 69 0 ": "sugarGrade",
    " 17 0 ": "statusCode",
    " 18 0 ": "returnIndicator",
    " 19 0 ": "supplierCode",
    " 23 0 ": "price",
    " 25 0 ": "priceSide",
    " 32 0 ": "promoStartDate",
    " 33 0 ": "promoEndDate",
    " 43 0 ": "stockOnHand",
    " 68 0 ": "rpType",
    " 70 0 ": "planogramInfo",
    " 72 0 ": "shortDescription",
    " 73 0 ": "supplySource",
    " 74 0 ": "supplySourceValue",
    " 75 0 ": "promoDescription",
    " 121 0 ": "itemIpf"
}


def get_glanogram_info(record):
    if jmespath.search("planogramInfoEntityList[0]", record):
        bay = jmespath.search("planogramInfoEntityList[0].bay", record)
        layerNumber = jmespath.search("planogramInfoEntityList[0].layerNumber", record)
        surfaceWidth = jmespath.search("planogramInfoEntityList[0].surfaceWidth", record)
        surfaceHeight = jmespath.search("planogramInfoEntityList[0].surfaceHeight", record)
        return f"{bay}-{layerNumber}-{surfaceWidth}/{surfaceHeight}"
    else:
        return ""


def get_sugar_grade(record):
    data = ""
    if jmespath.search("ware.tinyWare.extendInfo", record):
        sugarGrade = jmespath.search("ware.tinyWare.extendInfo.sugarGrade", record) or ""
        sugarGradeContent = jmespath.search("ware.tinyWare.extendInfo.sugarGradeContent", record) or ""
        if sugarGradeContent:
            sugarGradeContent += "%"
        data = sugarGrade + " " + sugarGradeContent
    return data


def get_item_size(record):
    """
    包装信息
    """
    data = jmespath.search("ware.packageVOList[0]", record)
    if not data: return ""
    return str(jmespath.search("ware.packageVOList[0].radio", record)) + " " + jmespath.search(
        "ware.packageVOList[0].packageUnit",
        record)


def get_supply_source_value(record):
    supply_source = jmespath.search("storePurchasesInfo.deliveryType", record)
    if supply_source == 0:
        # 在库
        return "Conventional"
    elif supply_source == 1:
        # 直流
        return "Flowthrough"
    elif supply_source == 2:
        # 直送
        return "DSP"
    elif supply_source == 12:
        # 越库
        return "CrossDock"
    return None


def get_pro_price(record):
    if "${itemIpf}" == "SIDE":
        return str(jmespath.search("promotions[*] |[0].rewardInfo.triggerRewardInfos[*].rewardValue|[0]", record) or "")
    return ""


def get_pro_desc(case_step_pro_info):
    if "${itemIpfApi}" in ("STOCKOUT", "NORMAL"):
        return ""
    if "${itemIpfApi}" == "YUU":
        # YUU会员促销 满件促销或者分类促销
        menber_pro = jmespath.search(
            '[0].memberOtherProInfos."2"[?proApplyUserLevels[0]==`2`[?proApplyUserLevels[0]==`2` && (proType==`3` || proType==`8`)]',
            case_step_pro_info) or []
        if not menber_pro:
            return ""
        return str(jmespath.search("[0].proSloganMap.en_US | [0]", menber_pro) or "")

    return str(jmespath.search("[0].commonProInfos|[0].proSloganMap.en_US | [0]", case_step_pro_info) or "")


def get_rptype(record):
    rptype = jmespath.search("ware.sapExtVO.extendInfo.rpType", record)
    rptype_map = {"0": "AO",
                  "1": "SGO",
                  "2": "MO",
                  "9": "ND"}
    return rptype_map.get(rptype, "")


def get_supply_code(record):
    code = jmespath.search("data.records[].storePurchasesInfo.supplierCode", record)
    if code and len(code) > 0:
        return code[0]
    return ""


file_temp = """
1001 $!item.barCode 4 0 |$!item.productCode| 6 0 |$!item.itemGroup| 7 0 |$!item.itemName| 8 0 |$!item.brand| 9 0 |$!item.category| 10 0 |$!item.subCategory| 11 0 |$!item.itemSize| 12 0 |$!item.itemUnit| 13 0 |$!item.itemOp| 17 0 |$!item.statusCode| 18 0 |$!item.returnIndicator| 19 0 |$!item.supplierCode| 23 0 |$!item.price| 25 0 |$!item.priceSide| 32 0 |$!item.promoStartDate| 33 0 |$!item.promoEndDate| 43 0 |$!item.stockOnHand| 68 0 |$!item.rpType| 69 0 |$!item.sugarGrade| 70 0 |$!item.planogramInfo| 72 0 |$!item.shortDescription| 73 0 |$!item.supplySource| 74 0 |$!item.supplySourceValue| 75 0 |$!item.promoDescription| 76 0 || 121 0 |$!item.itemIpf| ,
"""

file_content = """
1001 005013985 4 0 |5013985| 6 0 |101| 7 0 |LUNDBERG ORG BROWN BASMATI RICE 907G| 8 0 |LUNDBERG| 9 0 |10101| 10 0 |1010101| 11 0 |1 EA| 12 0 |PAC| 13 0 |1.000| 15 0 | | 16 0 |Y| 17 0 || 18 0 || 19 0 |11200649| 20 0 |9201| 21 0 |1| 22 0 || 23 0 |1090| 25 0 || 26 0 || 27 0 || 28 0 || 29 0 || 30 0 || 31 0 || 32 0 || 33 0 || 34 0 || 35 0 || 36 0 || 37 0 || 38 0 || 43 0 |0| 44 0 |0| 46 0 |0| 68 0 |AO| 70 0 || 71 0 |1| 121 0 |STOCKOUT|,
1001 20673416402030 4 0 |5013985| 6 0 |101| 7 0 |LUNDBERG ORG BROWN BASMATI RICE 907G| 8 0 |LUNDBERG| 9 0 |10101| 10 0 |1010101| 11 0 |1 EA| 12 0 |PAC| 13 0 |1.000| 15 0 | | 16 0 |Y| 17 0 || 18 0 || 19 0 |11200649| 20 0 |9201| 21 0 |1| 22 0 || 23 0 |1090| 25 0 || 26 0 || 27 0 || 28 0 || 29 0 || 30 0 || 31 0 || 32 0 || 33 0 || 34 0 || 35 0 || 36 0 || 37 0 || 38 0 || 43 0 |0| 44 0 |0| 46 0 |0| 68 0 |AO| 70 0 || 71 0 |1| 121 0 |STOCKOUT|,
1001 073416402034 4 0 |5013985| 6 0 |101| 7 0 |LUNDBERG ORG BROWN BASMATI RICE 907G| 8 0 |LUNDBERG| 9 0 |10101| 10 0 |1010101| 11 0 |1 EA| 12 0 |PAC| 13 0 |1.000| 15 0 | | 16 0 |Y| 17 0 || 18 0 || 19 0 |11200649| 20 0 |9201| 21 0 |1| 22 0 || 23 0 |1090| 25 0 || 26 0 || 27 0 || 28 0 || 29 0 || 30 0 || 31 0 || 32 0 || 33 0 || 34 0 || 35 0 || 36 0 || 37 0 || 38 0 || 43 0 |0| 44 0 |0| 46 0 |0| 68 0 |AO| 70 0 || 71 0 |1| 121 0 |STOCKOUT|,
"""

res_text = """
{
    "serverTime": "2024-12-02 10:30:22",
    "ip": "10.56.169.68:8080",
    "success": true,
    "code": "0000",
    "message": "success",
    "data": {
        "records": [
            {
                "id": 125473,
                "vendorId": 58989,
                "vendorCode": null,
                "vendorName": null,
                "storeId": 618858,
                "storeCode": null,
                "storeName": null,
                "skuId": 113822988,
                "timeline": "2024-12-02T10:30:21",
                "timelineUtc": 1733106621000,
                "effective": "2024-12-02T10:30:21",
                "effectiveUtc": 1733106621000,
                "orderType": null,
                "orderId": null,
                "proMantype": null,
                "createTime": null,
                "updateTime": null,
                "yn": 1,
                "version": null,
                "printed": null,
                "category1": "HB",
                "category2": "20",
                "category3": "2011",
                "category4": "201113",
                "category5": null,
                "multiCategory": "HB-20-201113-HAIR COLOR",
                "rangeInd": 1,
                "mcCode": "20111301",
                "saleFlag": 1,
                "brandId": 31887,
                "rxTag": 1,
                "wareType": null,
                "lowPriceFlag": null,
                "exclusiveBrandFlag": null,
                "skuCreateTime": null,
                "pushEsl": null,
                "changeReasonList": null,
                "priceChangeType": null,
                "zoneId": "Asia/Singapore",
                "ware": {
                    "sapVO": {
                        "matnr": "151131300",
                        "mstae": "0",
                        "mmsta": "2",
                        "retailPrice": {
                            "cent": 1000,
                            "currency": "SGD",
                            "centFactor": 100,
                            "currencyCode": "SGD",
                            "amount": 10.00
                        },
                        "offLinePrice": 10.00,
                        "offLinePriceFormat": "10,00",
                        "offLineRetailPrice": null,
                        "offLinePriceDecimal": null,
                        "offLinePriceDecimalFormat": null,
                        "offlineLocalCurrencyPrice": null,
                        "offlineLocalCurrencyPriceDecimal": null,
                        "offlineLocalCurrencyPriceDecimalFormat": "",
                        "nonDiscountableFlag": 0,
                        "priceStartTimeUtc": null,
                        "priceTime": "2024-11-26T06:02:31.024+00:00"
                    },
                    "sapExtVO": {
                        "rangeInd": 1,
                        "supplierCode": null,
                        "mainSupplierCode": null,
                        "sellType": 1,
                        "isUnionNo": false,
                        "suf": null,
                        "canSale": true,
                        "extendInfo": {
                            "rpType": "1",
                            "minDisplayQty": 99
                        }
                    },
                    "wareMatnrItemNumVOList": [
                        {
                            "venderId": 58989,
                            "matnr": "151131300",
                            "itemNum": "14987205947534",
                            "mainItemNum": 0,
                            "ratio": 1,
                            "packageRtio": 1,
                            "packageName": null,
                            "packageId": "EA"
                        },
                        {
                            "venderId": 58989,
                            "matnr": "151131300",
                            "itemNum": "4987205947537",
                            "mainItemNum": 1,
                            "ratio": 1,
                            "packageRtio": 1,
                            "packageName": null,
                            "packageId": "EA"
                        },
                        {
                            "venderId": 58989,
                            "matnr": "151131300",
                            "itemNum": "151131300",
                            "mainItemNum": 0,
                            "ratio": 1,
                            "packageRtio": 1,
                            "packageName": null,
                            "packageId": "EA"
                        }
                    ],
                    "extVO": {
                        "specQty": "1Box",
                        "specUnit": "",
                        "produceArea": "1",
                        "grade": null
                    },
                    "tinyWare": {
                        "titleDesc": "BIGEN SPEEDY #881 NAT BLACK",
                        "title": "BIGEN SPEEDY #881 NAT BLACK",
                        "sapTitle": "BIGEN SPEEDY #881 NAT BLACK",
                        "chine": "EA",
                        "customRemark": null,
                        "packUnit": "EA",
                        "orderSpec": null,
                        "returnDate": null,
                        "externalCode": "151131300",
                        "produceArea": "1",
                        "frontUnitIdExt": null,
                        "frontUnitId": "EA",
                        "weight": 0,
                        "brandId": 31887,
                        "brandName": " ",
                        "mcCode": "20111301",
                        "wareStatus": 1,
                        "jlineFlag": null,
                        "top1000Ind": null,
                        "slowMovingInd": null,
                        "privateLabelInd": null,
                        "productGrading": null,
                        "supplierId": null,
                        "supplyChannel": null,
                        "orderConversion": null,
                        "nutritionCode": null,
                        "dfWareStatus": 1,
                        "dcType0": null,
                        "dcType1": null,
                        "wareLife": 0.0,
                        "wareLifeUnit": 1,
                        "specType": 0,
                        "extendInfo": {
                            "articleType": "0",
                            "alcoholFlag": 0
                        },
                        "catExtendInfo": {},
                        "languageDocMap": {
                            "zh_HK": {
                                "sap_title": "BIGEN SPEEDY #881 NAT BLACK",
                                "cn_name": "null data",
                                "ad": null,
                                "cat_name": null,
                                "expand_attributes": null,
                                "ad_url": null,
                                "chine": "EA",
                                "title_plu_text": "BIGEN SPEEDY #881 NAT BLACK",
                                "packing_specification": "1Box",
                                "title": "BIGEN SPEEDY #881 NAT BLACK",
                                "title_desc": "BIGEN SPEEDY #881 NAT BLACK",
                                "title_web_desc": "BIGEN SPEEDY #881 NAT BLACK"
                            },
                            "en_US": {
                                "sap_title": "BIGEN SPEEDY #881 NAT BLACK",
                                "ad": null,
                                "cat_name": null,
                                "ad_url": null,
                                "title_plu_text": "BIGEN SPEEDY #881 NAT BLACK",
                                "title": "BIGEN SPEEDY #881 NAT BLACK",
                                "cn_name": "null data",
                                "expand_attributes": null,
                                "chine": "EA",
                                "original_title_web_desc": "BIGEN SPEEDY #881 NAT BLACK",
                                "packing_specification": "1Box",
                                "title_desc": "BIGEN SPEEDY #881 NAT BLACK",
                                "title_web_desc": "BIGEN SPEEDY #881 NAT BLACK"
                            },
                            "zh_CN": {
                                "sap_title": "BIGEN SPEEDY #881 NAT BLACK",
                                "cn_name": "null data",
                                "ad": null,
                                "cat_name": null,
                                "expand_attributes": null,
                                "ad_url": null,
                                "chine": "EA",
                                "title_plu_text": "BIGEN SPEEDY #881 NAT BLACK",
                                "packing_specification": "1Box",
                                "title": "BIGEN SPEEDY #881 NAT BLACK",
                                "title_desc": "BIGEN SPEEDY #881 NAT BLACK",
                                "title_web_desc": "BIGEN SPEEDY #881 NAT BLACK"
                            },
                            "km_KH": {
                                "sap_title": "BIGEN SPEEDY #881 NAT BLACK",
                                "cn_name": "null data",
                                "ad": null,
                                "cat_name": null,
                                "expand_attributes": null,
                                "ad_url": null,
                                "chine": "EA",
                                "title_plu_text": "BIGEN SPEEDY #881 NAT BLACK",
                                "packing_specification": "1Box",
                                "title": "BIGEN SPEEDY #881 NAT BLACK",
                                "title_desc": "BIGEN SPEEDY #881 NAT BLACK",
                                "title_web_desc": "BIGEN SPEEDY #881 NAT BLACK"
                            }
                        },
                        "wareLanguage": {
                            "zh_HK": "BIGEN SPEEDY #881 NAT BLACK",
                            "en_US": "BIGEN SPEEDY #881 NAT BLACK",
                            "zh_CN": "BIGEN SPEEDY #881 NAT BLACK",
                            "km_KH": "BIGEN SPEEDY #881 NAT BLACK"
                        },
                        "flowthruIndicator": 0,
                        "coreRange": null,
                        "nonDiscountableFlag": null,
                        "alcoholItemFlag": 0,
                        "frontUnitIdKG": ""
                    },
                    "itemNum": "4987205947537",
                    "brand": {
                        "lang": {
                            "zh_HK": {
                                "cn_name": " ",
                                "other_name": " "
                            },
                            "en_US": {
                                "cn_name": " ",
                                "other_name": " "
                            },
                            "km_KH": {
                                "cn_name": " ",
                                "other_name": " "
                            }
                        }
                    },
                    "wareId": 106703013,
                    "skuId": 113822988,
                    "packageVOList": [
                        {
                            "id": 76252038,
                            "skuId": 113822988,
                            "packageUnit": "EA",
                            "radio": 1,
                            "begrew": 0.000,
                            "canSale": true,
                            "length": 0.000,
                            "width": 0.000,
                            "height": 0.000,
                            "volume": null,
                            "cubage": null,
                            "color": null,
                            "venderId": 58989,
                            "matnr": "151131300",
                            "name": "default",
                            "type": 0
                        },
                        {
                            "id": 76252088,
                            "skuId": 113822988,
                            "packageUnit": "H01",
                            "radio": 1,
                            "begrew": 0.000,
                            "canSale": true,
                            "length": 0.000,
                            "width": 0.000,
                            "height": 0.000,
                            "volume": null,
                            "cubage": null,
                            "color": null,
                            "venderId": 58989,
                            "matnr": "151131300",
                            "name": "H01",
                            "type": null
                        }
                    ],
                    "garfield": null,
                    "promotionPriceFlag": null,
                    "baseStatusVO": {
                        "id": 1088,
                        "venderId": null,
                        "statusCode": "2",
                        "statusName": "Delete",
                        "orderAble": true,
                        "returnAble": true,
                        "shopAllotAble": null,
                        "saleReturnAble": true,
                        "exhibitAble": false,
                        "isShopDefault": null,
                        "autoOrderAble": false,
                        "shopManualOrderAble": false,
                        "comManualOrderAble": null,
                        "proGoodsOrderAble": false,
                        "authorizationReturn": true,
                        "stockAdjustAble": true,
                        "stocktake": true,
                        "printShelfLabel": true,
                        "printMarkdownLabel": true
                    },
                    "wareTypeCfgVO": {
                        "wareTypeCode": "PTSP",
                        "subTypeCode": null,
                        "wareSpecCode": 0,
                        "sellTypeCode": 1,
                        "orderAble": 1,
                        "sellOnlineAble": null,
                        "sellOfflineAble": 1,
                        "sortIdx": 0,
                        "wareTypeName": null,
                        "subTypeName": null,
                        "wareSpecName": "普通商品",
                        "sellTypeName": "自营",
                        "id": 213,
                        "stockAble": 1,
                        "stockWithCost": 1,
                        "stockWithAmount": 1,
                        "stockTypeCode": null,
                        "stockTypeName": null
                    }
                },
                "promotions": [],
                "ypromotions": null,
                "categories": [
                    {
                        "id": 9651708,
                        "parentId": null,
                        "code": "HB",
                        "name": "Health & Beauty",
                        "level": 1,
                        "totalLevel": 1,
                        "isLeaf": false,
                        "catType": 3,
                        "shopType": 13,
                        "parent": null,
                        "children": null,
                        "originCatType": 0
                    },
                    {
                        "id": 9651728,
                        "parentId": 9651708,
                        "code": "20",
                        "name": "PERSONAL CARE",
                        "level": 2,
                        "totalLevel": 2,
                        "isLeaf": false,
                        "catType": 3,
                        "shopType": 13,
                        "parent": null,
                        "children": null,
                        "originCatType": 0
                    },
                    {
                        "id": 9651743,
                        "parentId": 9651728,
                        "code": "2011",
                        "name": "HAIR CARE",
                        "level": 3,
                        "totalLevel": 3,
                        "isLeaf": false,
                        "catType": 3,
                        "shopType": 13,
                        "parent": null,
                        "children": null,
                        "originCatType": 0
                    },
                    {
                        "id": 9651788,
                        "parentId": 9651743,
                        "code": "201113",
                        "name": "HAIR COLOR",
                        "level": 4,
                        "totalLevel": 4,
                        "isLeaf": true,
                        "catType": 3,
                        "shopType": 13,
                        "parent": null,
                        "children": null,
                        "originCatType": 0
                    },
                    {
                        "id": 18789148,
                        "parentId": 9651788,
                        "code": "20111301",
                        "name": "PERMANENT COLOR",
                        "level": 1,
                        "totalLevel": 5,
                        "isLeaf": true,
                        "catType": 3,
                        "shopType": 0,
                        "parent": null,
                        "children": null,
                        "originCatType": 3
                    }
                ],
                "templates": {},
                "coinConfigInfo": {
                    "transactionCurrency": "SGD",
                    "unitCostScale": 2,
                    "currencyCoef": 100
                },
                "coinConfigInfoLocal": {
                    "transactionCurrency": "SGD",
                    "unitCostScale": 2,
                    "currencyCoef": 100
                },
                "pogId": null,
                "planogramInfoEntityList": null,
                "pogInfo": null,
                "extraDataInfo": {
                    "id": null,
                    "vendorId": null,
                    "storeId": null,
                    "wareCode": null,
                    "top250": null,
                    "top500": null,
                    "top1000": null,
                    "avgDailySalesQty": null,
                    "stockOnHand": null,
                    "onOrderQty": null,
                    "availableSoh": null,
                    "inTransitStock": null,
                    "stockStatus": null,
                    "stockVersion": null,
                    "supplierCode": null,
                    "dummyCode": null,
                    "centralPurchasingFlag": null,
                    "creatorId": null,
                    "creatorName": null,
                    "created": null,
                    "modifierId": null,
                    "modifierName": null,
                    "modified": null
                },
                "historicalPriceList": null,
                "largeAre": null,
                "stockAndSaleVo": {
                    "saleInfo": "YES",
                    "stockInfo": "NO"
                },
                "bestPro": false,
                "userTypes": null,
                "storePurchasesInfo": {
                    "deliveryType": 0,
                    "returnIndicator": null,
                    "minOrderQty": null,
                    "orderCalendar": null,
                    "supplierCode": null,
                    "supplierName": null,
                    "bizType": null
                },
                "amountFormatVo": {
                    "separator": ".",
                    "decimal": ",",
                    "zero": 0,
                    "precision": 2,
                    "currencyCoef": 100
                }
            }
        ],
        "total": 1,
        "size": 20,
        "current": 1,
        "orders": [],
        "optimizeCountSql": true,
        "searchCount": true,
        "countId": null,
        "maxLimit": null,
        "pages": 1
    },
    "total": null,
    "pageNum": null,
    "pageSize": null,
    "totalPage": null
}
"""


def get_file_content_map_ftp(file_contents: str) -> dict:
    file_contents_map = {}
    file_lines = file_contents.split("\n")
    for line in file_lines:
        if not line or not line.strip():
            continue
        item_code = line.strip().split("|")[1]
        file_contents_map[item_code] = f'{line.split(" ", maxsplit=2)[2:-2]}'
    return file_contents_map


def map2str_ftp(map_content: dict) -> str:
    str_list = []
    for key, value in map_content.items():
        str_list.append(f"{key}|{value}")
    return "|".join(str_list)


def get_file_content_map_api(file_contents: str) -> dict:
    file_contents_map = {}
    file_lines = file_contents.split("\n")
    for line in file_lines:
        if not line or not line.strip():
            continue
        item_code = line.strip().split("|")[1]
        file_contents_map[item_code] = line.split("|", maxsplit=1)[1]
    return file_contents_map


def map2str_api(map_content: dict) -> str:
    return "|".join(map_content.values())


def gen_map_ftp(line_str, is_temp=False):
    key_map = {}
    new_temp = " ".join(line_str.strip().split(" ")[2:])
    temp_list = new_temp.split("|")
    for index in range(0, len(temp_list) - 1, 2):
        c_value = temp_list[index + 1]
        if is_temp:
            c_value = c_value.split(".")[-1]
        key_map[temp_list[index]] = c_value
    return key_map


# res_text = apt.data.result.response.text
res = json.loads(res_text)
record = res["data"]["records"][0]

# ware = record["ware"]
# promotions = record["promotions"]  categories[?level==`2`].code | [0]

current_map = {
    "4 0 ": jmespath.search("ware.sapVO.matnr", record),
    " 6 0 ": jmespath.search("categories[?level==`2`].code | [0]", record),
    " 7 0 ": jmespath.search("ware.tinyWare.wareLanguage.en_US", record),
    " 8 0 ": jmespath.search("ware.brand.lang.en_US.cn_name", record),
    " 9 0 ": jmespath.search("categories[?level==`3`].code | [0]", record),
    " 10 0 ": jmespath.search("categories[?level==`4`].code | [0]", record),
    " 11 0 ": get_item_size(record),
    " 12 0 ": jmespath.search("ware.tinyWare.frontUnitId", record),
    " 13 0 ": jmespath.search("ware.extVO.specQty", record) or "",
    " 17 0 ": jmespath.search("ware.sapVO.mmsta", record),
    " 18 0 ": "",
    " 19 0 ": get_supply_code(record),
    " 23 0 ": str(jmespath.search("ware.sapVO.retailPrice.cent", record) or ""),
    " 25 0 ": get_pro_price(record),
    " 32 0 ": "${proStartTime}",
    " 33 0 ": "${proEndTime}",
    " 43 0 ": jmespath.search("extraDataInfo.stockOnHand", record) or "",
    " 68 0 ": get_rptype(record),
    " 69 0 ": get_sugar_grade(record),
    " 70 0 ": get_glanogram_info(record),
    " 72 0 ": jmespath.search("ware.tinyWare.languageDocMap.en_US.sap_title", record),
    " 73 0 ": f'{jmespath.search("storePurchasesInfo.deliveryType", record)}',
    " 74 0 ": "",
    " 75 0 ": get_pro_desc(record),
    " 121 0 ": "itemIpf"
}

api_data = {
    "4 0 ": jmespath.search("ware.sapVO.matnr", record),
    " 7 0 ": jmespath.search("ware.tinyWare.wareLanguage.en_US", record),
    " 8 0 ": jmespath.search("ware.brand.lang.en_US.cn_name", record),
    " 9 0 ": jmespath.search("categories[?level==`3`].code | [0]", record),
    " 10 0 ": jmespath.search("categories[?level==`4`].code | [0]", record),
    " 11 0 ": get_item_size(record),
    " 12 0 ": jmespath.search("ware.tinyWare.frontUnitId", record),
    " 13 0 ": jmespath.search("ware.extVO.specQty", record) or "",
    " 69 0 ": get_sugar_grade(record),
    " 17 0 ": jmespath.search("ware.sapVO.mmsta", record),
    " 18 0 ": "",
    " 19 0 ": jmespath.search("extraDataInfo.supplierCode", record) or "",
    " 23 0 ": str(jmespath.search("ware.sapVO.retailPrice.cent", record) or ""),
    " 25 0 ": get_pro_price(record),
    " 32 0 ": "${proStartTime}",
    " 33 0 ": "${proEndTime}",
    " 43 0 ": jmespath.search("extraDataInfo.stockOnHand", record) or "",
    " 68 0 ": get_rptype(record),
    " 70 0 ": get_glanogram_info(record),
    " 72 0 ": jmespath.search("ware.tinyWare.languageDocMap.en_US.sap_title", record),
    " 73 0 ": f'{jmespath.search("storePurchasesInfo.deliveryType", record)}',
    " 74 0 ": "",
    " 75 0 ": get_pro_desc(record),
    " 121 0 ": "${itemIpf}"
}

# productCode = jmespath.search("ware.sapVO.matnr", record)[2:]
# item_proup = jmespath.search("categories[?level==`2`].code | [0]", record)
# item_name = jmespath.search("ware.tinyWare.wareLanguage.en_US", record)
# brand = jmespath.search("ware.brand.lang.en_US.cn_name", record)
# category = jmespath.search("categories[?level==`3`].code | [0]", record)
# sub_category = jmespath.search("categories[?level==`4`].code | [0]", record)
# item_size = str(jmespath.search("ware.packageVOList[0].radio", record)) + jmespath.search("ware.packageVOList[0].packageUnit", record)

# assertC(productCode == 111, "", f"{productCode} == {111}")
# assertC(item_proup == 111, "", f"{item_proup} == {111}")
# assertC(item_name == 111, "", f"{item_name} == {111}")
# assertC(brand == 111, "", f"{brand} == {111}")
# assertC(category == 111, "", f"{category} == {111}")
# assertC(sub_category == 111, "", f"{sub_category} == {111}")
# assertC(item_size == 111, "", f"{item_size} == {111}")

# logger.info(apt.case_variables["ftp_file_content"])

payment_display_data = """
{
    "successful": true,
    "code": "0000",
    "msg": "请求成功",
    "displayMsg": null,
    "data": [
        {
            "id": 3813,
            "vendorId": 11,
            "psId": 1,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"現金\",\"en_US\":\"Cash\"}",
            "psCurrentLanguageName": "現金",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 1,
            "yn": 1
        },
        {
            "id": 3818,
            "vendorId": 11,
            "psId": 3,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"人民幣\",\"en_US\":\"RMB\"}",
            "psCurrentLanguageName": "人民幣",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 2,
            "yn": 1
        },
        {
            "id": 3823,
            "vendorId": 11,
            "psId": 4,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"信用卡\",\"en_US\":\"Credit Card\"}",
            "psCurrentLanguageName": "信用卡",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 3,
            "yn": 1
        },
        {
            "id": 3828,
            "vendorId": 11,
            "psId": 5,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"信用卡積分\",\"en_US\":\"Credit Card Points\"}",
            "psCurrentLanguageName": "信用卡積分",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 4,
            "yn": 1
        },
        {
            "id": 3833,
            "vendorId": 11,
            "psId": 6,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"銀聯\",\"en_US\":\"UnionPay\"}",
            "psCurrentLanguageName": "銀聯",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 5,
            "yn": 1
        },
        {
            "id": 3838,
            "vendorId": 11,
            "psId": 7,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"八達通\",\"en_US\":\"Octopus\"}",
            "psCurrentLanguageName": "八達通",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 6,
            "yn": 1
        },
        {
            "id": 3843,
            "vendorId": 11,
            "psId": 9,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"易辦事\",\"en_US\":\"EPS\"}",
            "psCurrentLanguageName": "易辦事",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 7,
            "yn": 1
        },
        {
            "id": 3853,
            "vendorId": 11,
            "psId": 11,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"enJoy卡折扣\",\"en_US\":\"enJoy Discount\",\"zh_CN\":\"enJoy卡折扣\"}",
            "psCurrentLanguageName": "enJoy卡折扣",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 8,
            "yn": 1
        },
        {
            "id": 3858,
            "vendorId": 11,
            "psId": 17,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"Enjoy 獎賞現金券\",\"en_US\":\"EnJoy Reward\"}",
            "psCurrentLanguageName": "Enjoy 獎賞現金券",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 9,
            "yn": 1
        },
        {
            "id": 3878,
            "vendorId": 11,
            "psId": 114,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\" 港幣\",\"en_US\":\"Hong Kong Dollar\"}",
            "psCurrentLanguageName": " 港幣",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 10,
            "yn": 1
        },
        {
            "id": 3883,
            "vendorId": 11,
            "psId": 116,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"澳門通\",\"en_US\":\"Macau Pass\"}",
            "psCurrentLanguageName": "澳門通",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 11,
            "yn": 1
        },
        {
            "id": 3913,
            "vendorId": 11,
            "psId": 184,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"澳門錢包\",\"en_US\":\"Mpay\"}",
            "psCurrentLanguageName": "澳門錢包",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 12,
            "yn": 1
        },
        {
            "id": 3908,
            "vendorId": 11,
            "psId": 183,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"支付寶（中國）\",\"en_US\":\"Alipay(China)\"}",
            "psCurrentLanguageName": "支付寶（中國）",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 13,
            "yn": 1
        },
        {
            "id": 3983,
            "vendorId": 11,
            "psId": 185,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"聚易用\",\"en_US\":\"SimplePay\"}",
            "psCurrentLanguageName": "聚易用",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 14,
            "yn": 1
        },
        {
            "id": 3848,
            "vendorId": 11,
            "psId": 8,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"QR支付\",\"en_US\":\"QR Payment\"}",
            "psCurrentLanguageName": "QR支付",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 15,
            "yn": 1
        },
        {
            "id": 3898,
            "vendorId": 11,
            "psId": 180,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"TNG\",\"en_US\":\"TNG\"}",
            "psCurrentLanguageName": "TNG",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 16,
            "yn": 1
        },
        {
            "id": 3903,
            "vendorId": 11,
            "psId": 182,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"Tap&go\",\"en_US\":\"Tap&go\"}",
            "psCurrentLanguageName": "Tap&go",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 17,
            "yn": 1
        },
        {
            "id": 3873,
            "vendorId": 11,
            "psId": 26,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"yuu 現金券\",\"en_US\":\"yuu Cash Voucher\"}",
            "psCurrentLanguageName": "yuu 現金券",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 19,
            "yn": 1
        },
        {
            "id": 3923,
            "vendorId": 11,
            "psId": 191,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"711電子優惠券\",\"en_US\":\"711 e-voucher\"}",
            "psCurrentLanguageName": "711電子優惠券",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 20,
            "yn": 1
        },
        {
            "id": 3928,
            "vendorId": 11,
            "psId": 192,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"禮券\",\"en_US\":\"711 Gift Voucher\"}",
            "psCurrentLanguageName": "禮券",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 22,
            "yn": 1
        },
        {
            "id": 3863,
            "vendorId": 11,
            "psId": 19,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"商場券1\",\"en_US\":\"landlord coupon1\"}",
            "psCurrentLanguageName": "商場券1",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 23,
            "yn": 1
        },
        {
            "id": 3868,
            "vendorId": 11,
            "psId": 20,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"商場券2\",\"en_US\":\"landlord coupon2\"}",
            "psCurrentLanguageName": "商場券2",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 24,
            "yn": 1
        },
        {
            "id": 3933,
            "vendorId": 11,
            "psId": 193,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"八達通流動入數\",\"en_US\":\"Mobile Octopus\"}",
            "psCurrentLanguageName": "八達通流動入數",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 25,
            "yn": 1
        },
        {
            "id": 3893,
            "vendorId": 11,
            "psId": 124,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"澳覓\",\"en_US\":\"Aomei\"}",
            "psCurrentLanguageName": "澳覓",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 26,
            "yn": 1
        },
        {
            "id": 3938,
            "vendorId": 11,
            "psId": 205,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"foodpanda\",\"en_US\":\"foodpanda\"}",
            "psCurrentLanguageName": "foodpanda",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 27,
            "yn": 1
        },
        {
            "id": 3943,
            "vendorId": 11,
            "psId": 252,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"M FOOD\",\"en_US\":\"M FOOD\"}",
            "psCurrentLanguageName": "M FOOD",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 28,
            "yn": 1
        },
        {
            "id": null,
            "vendorId": 11,
            "psId": 129,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"日圓\",\"en_US\":\"Japanese Yen\"}",
            "psCurrentLanguageName": "日圓",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 100,
            "yn": 1
        },
        {
            "id": null,
            "vendorId": 11,
            "psId": 131,
            "posType": 1,
            "psDisplayName": "{\"zh_HK\":\"美元\",\"en_US\":\"United States dollar\"}",
            "psCurrentLanguageName": "美元",
            "displayType": 1,
            "displayGroup": null,
            "displayIndex": 100,
            "yn": 1
        }
    ]
}
"""


def get_psid_from_displaydata(data):
    json_data = json.loads(data)
    json_data = json_data['data']
    ps_id = []
    for item in json_data:
        ps_id.append(item['psId'])
    print(",".join(ps_id))


all_times = {}
current_done_index = 0

def check_status(i, client_id, headers, start_time):
    global current_done_index
    is_done = False
    error_num = 0
    while not is_done:
        try:
            # https://newpricetag-partner.rta-os.com/api/print/async/info
            res_status = requests.request(
                "GET",
                "http://newpricetag-partner.rta-os.com/api/print/async/info",
                params={"clientId": client_id},
                headers=headers)
            time.sleep(3)
            if res_status.json()["data"]["status"] == "done":
                lock.acquire_lock()
                current_done_index = current_done_index + 1
                long_time = datetime.datetime.now() - start_time
                print(f"已经完成 {str(current_done_index):^4} 条， 第{str(i+1):^4} 【{client_id}】次打印使用时间：{long_time}")
                is_done = True
                all_times[client_id] = long_time.seconds
                lock.release()
        except Exception as e:
            time.sleep(1)
            error_num += 1


def pricetag_test(concurrent_num=10):

    """
    测试环境的数据
    %7B%22selectParam%22%3A%7B%22printed%22%3A%22%22%2C%22end%22%3A1742977208000%2C%22orderNoType%22%3A10%2C%22orderNos%22%3Anull%2C%22brandId%22%3Anull%2C%22pogType%22%3A-1%2C%22shelvesCodes%22%3Anull%2C%22storeId%22%3A%2221%22%2C%22deptOp%22%3A1%2C%22deptIdList%22%3A%5B%225%22%2C%226%22%2C%2299%22%2C%22LogTest2%22%5D%2C%22deptLevel%22%3A1%2C%22effectTimes%22%3A%5B%5D%2C%22mainType%22%3A%5B%5D%2C%22selectedChangeReasonList%22%3A%5B%5D%2C%22current%22%3A1%2C%22size%22%3A20%2C%22sortField%22%3A%22pog_id%22%2C%22sortOrder%22%3A%22asc%22%2C%22layoutId%22%3A153%2C%22priceTagType%22%3A2%2C%22tab%22%3A2%2C%22effectiveStartPoint%22%3Anull%2C%22effectiveEndPoint%22%3Anull%2C%22selectedPriceChangeTypeList%22%3A%5B%5D%2C%22queryStockAndSaleFlag%22%3A1%2C%22checkedWareItemStatus%22%3A%5B%5D%2C%22pogNameList%22%3A%5B%5D%2C%22scaleHalf%22%3A1%2C%22printType%22%3A%220%22%2C%22forceFlag%22%3Afalse%2C%22print%22%3Atrue%2C%22selectedPogLocation%22%3Atrue%7D%2C%22settings%22%3A%5B%5D%7D

    """
    start_time = datetime.datetime.now()
    print(f"开始打印的时间{start_time}")
    headers = {
        "Cookie": 'menu_route_key=5; returnUrl=http://idms.db.rta-os.com/#/mysql/mysql_query?instance_id=1297&instance_name=%25E6%2596%25B0%25E4%25BB%25B7%25E7%25AD%25BE%25E7%25B3%25BB%25E7%25BB%259F%25E5%2590%258E%25E7%25AB%25AF-%25E6%2596%25B0%25E4%25BB%25B7%25E7%25AD%25BE%25E7%25B3%25BB%25E7%25BB%259F%25EF%25BC%2588API%25E7%25AB%25AF%25EF%25BC%2589%2C%25E6%2596%25B0%25E4%25BB%25B7%25E7%25AD%25BE%25E7%25B3%25BB%25E7%25BB%259F%25EF%25BC%2588MAN%25E7%25AB%25AF%2520%253E%2520rta_price_tag&env_type=pro&env_type_display=pro&db_name=rta_price_tag&type=mysql; aladdin_gray=; HWWAFSESTIME=1742212174397; HWWAFSESID=58c3d76a7e9f681a99; __token_="SEg6bW0jIzExOS42Ljk3LjM3IyNISDptbSMjMzFiNTIjIzNGRDJGMTdFMzA3OTBEMTU3MDA5NEY3NDAyNzUyQjRCRUU0NTZERTlDNUFGQzQyMDk4QTk0QTgxNEE2MUYwQkExQTZFNTkwMzc2RkIzOEUzMjZFODlEMUQzNDg2QzkyOTc5REFBNEI1NjVFQ0NFMjNFRTdBNjgxQUY2OTk4Mjk5RTgxQzgyMTk4M0M5MDk1MTFDOEZFM0IzQjE0MTM4RkY4MTRGNkI4QjdBMkNDMTM1RDZDRTgxRDdCMTQ2RkM4RkYxQUNFOURDRTQyRjYzQ0Y2QjBGQUMwOTM3Q0Y1NTMyRkNGRUMyRjNGRjNENDVCNjEwMEEyOTZENzA0NUQzNDQ="; rta-os_vender=3; venderId=3; dmall-locale=zh_HK',
        "Host": "newpricetag-partner.rta-os.com",
        "Origin": "https://partner.rta-os.com",
        "Referer": "https://partner.rta-os.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Connection": "close",
        # "graytoken": "gray"
    }
    client_ids = []
    ip_set= defaultdict(int)
    for i in range(concurrent_num):
        try:
            index = i
            start_time = datetime.datetime.now()
            res = requests.post("https://newpricetag-partner.rta-os.com/api/print/all/async",
                                data={
                                    # 5千多品
                                    # "json": "%7B%22selectParam%22%3A%7B%22printed%22%3A%22%22%2C%22end%22%3A1742913596000%2C%22orderNoType%22%3A10%2C%22orderNos%22%3Anull%2C%22brandId%22%3Anull%2C%22pogType%22%3A-1%2C%22shelvesCodes%22%3Anull%2C%22storeId%22%3A%223%22%2C%22deptOp%22%3A1%2C%22deptIdList%22%3A%5B%2204%22%2C%2211%22%5D%2C%22deptLevel%22%3A2%2C%22effectTimes%22%3A%5B%5D%2C%22mainType%22%3A%5B%5D%2C%22selectedChangeReasonList%22%3A%5B%5D%2C%22current%22%3A1%2C%22size%22%3A20%2C%22sortField%22%3A%22pog_id%22%2C%22sortOrder%22%3A%22asc%22%2C%22layoutId%22%3A73%2C%22priceTagType%22%3A2%2C%22tab%22%3A2%2C%22effectiveStartPoint%22%3Anull%2C%22effectiveEndPoint%22%3Anull%2C%22selectedPriceChangeTypeList%22%3A%5B%5D%2C%22queryStockAndSaleFlag%22%3A-1%2C%22checkedWareItemStatus%22%3A%5B%5D%2C%22pogNameList%22%3A%5B%5D%2C%22scaleHalf%22%3A1%2C%22printType%22%3A%220%22%2C%22forceFlag%22%3Atrue%2C%22print%22%3Atrue%2C%22selectedPogLocation%22%3Atrue%7D%2C%22settings%22%3A%5B%5D%7D"
                                    # 单品
                                    # "json": "%7B%22selectParam%22%3A%7B%22printed%22%3A%22%22%2C%22end%22%3A1742907834000%2C%22orderNoType%22%3A10%2C%22orderNos%22%3A%5B%22766956%22%5D%2C%22brandId%22%3Anull%2C%22pogType%22%3A-1%2C%22shelvesCodes%22%3Anull%2C%22storeId%22%3A%223%22%2C%22deptOp%22%3A1%2C%22deptIdList%22%3A%5B%5D%2C%22effectTimes%22%3A%5B%5D%2C%22mainType%22%3A%5B%5D%2C%22selectedChangeReasonList%22%3A%5B%5D%2C%22current%22%3A1%2C%22size%22%3A20%2C%22sortField%22%3A%22pog_id%22%2C%22sortOrder%22%3A%22asc%22%2C%22layoutId%22%3A73%2C%22priceTagType%22%3A2%2C%22tab%22%3A2%2C%22effectiveStartPoint%22%3Anull%2C%22effectiveEndPoint%22%3Anull%2C%22selectedPriceChangeTypeList%22%3A%5B%5D%2C%22queryStockAndSaleFlag%22%3A-1%2C%22checkedWareItemStatus%22%3A%5B%5D%2C%22pogNameList%22%3A%5B%5D%2C%22scaleHalf%22%3A1%2C%22printType%22%3A%220%22%2C%22forceFlag%22%3Atrue%2C%22print%22%3Atrue%2C%22selectedPogLocation%22%3Atrue%7D%2C%22settings%22%3A%5B%5D%7D"
                                    #3千8百多品
                                    "json": "%7B%22selectParam%22%3A%7B%22printed%22%3A%22%22%2C%22end%22%3A1742926830000%2C%22orderNoType%22%3A10%2C%22orderNos%22%3Anull%2C%22brandId%22%3Anull%2C%22pogType%22%3A-1%2C%22shelvesCodes%22%3Anull%2C%22storeId%22%3A%223%22%2C%22deptOp%22%3A1%2C%22deptIdList%22%3A%5B%2206%22%5D%2C%22deptLevel%22%3A2%2C%22effectTimes%22%3A%5B%5D%2C%22mainType%22%3A%5B%5D%2C%22selectedChangeReasonList%22%3A%5B%5D%2C%22current%22%3A1%2C%22size%22%3A20%2C%22sortField%22%3A%22pog_id%22%2C%22sortOrder%22%3A%22asc%22%2C%22layoutId%22%3A73%2C%22priceTagType%22%3A2%2C%22tab%22%3A2%2C%22effectiveStartPoint%22%3Anull%2C%22effectiveEndPoint%22%3Anull%2C%22selectedPriceChangeTypeList%22%3A%5B%5D%2C%22queryStockAndSaleFlag%22%3A-1%2C%22checkedWareItemStatus%22%3A%5B%5D%2C%22pogNameList%22%3A%5B%5D%2C%22scaleHalf%22%3A1%2C%22printType%22%3A%220%22%2C%22forceFlag%22%3Atrue%2C%22print%22%3Atrue%2C%22selectedPogLocation%22%3Atrue%7D%2C%22settings%22%3A%5B%5D%7D"
                                },
                                headers=headers
                                )
            res_data = res.json()
            client_id = res_data["data"]
            ip = res_data["ip"]
            ip_set[ip] += 1

            # print(f"第 {i} 次请求的ID {client_id}")
            client_ids.append((index, client_id, headers, start_time))
        except Exception as pe:
            print(f"第{i}次打印失败： {pe}")
    print(json.dumps(ip_set, ensure_ascii=False, indent=4))
    print(f"打印请求完成，开始检查状态的时间{datetime.datetime.now()}")
    # with ThreadPoolExecutor(max_workers=200) as executor:
    #     for request_info in client_ids:
    #         executor.submit(check_status, *request_info)

    threads = []
    for request_info in client_ids:
        threads.append(threading.Thread(target=check_status, args=request_info))

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()
    print(f"打印结束时间:{datetime.datetime.now()}")
    print(f"共耗时:{datetime.datetime.now()-start_time}")


def check_ip(headers):
    count = defaultdict(int)
    for i in range(10):
        try:
            res_status = requests.request(
                "GET",
                "http://newpricetag-partner.rta-os.com/common/printType",
                headers=headers)
            if res_status.status_code == 200:
                ip = res_status.json()['ip']
                # print(ip)
                count[ip] += 1

        except Exception as e:
            pass

    print(count)



if __name__ == "__main__":
    lock = threading.Lock()
    headers = {
        "Cookie": 'menu_route_key=5; returnUrl=http://idms.db.rta-os.com/#/mysql/mysql_query?instance_id=1297&instance_name=%25E6%2596%25B0%25E4%25BB%25B7%25E7%25AD%25BE%25E7%25B3%25BB%25E7%25BB%259F%25E5%2590%258E%25E7%25AB%25AF-%25E6%2596%25B0%25E4%25BB%25B7%25E7%25AD%25BE%25E7%25B3%25BB%25E7%25BB%259F%25EF%25BC%2588API%25E7%25AB%25AF%25EF%25BC%2589%2C%25E6%2596%25B0%25E4%25BB%25B7%25E7%25AD%25BE%25E7%25B3%25BB%25E7%25BB%259F%25EF%25BC%2588MAN%25E7%25AB%25AF%2520%253E%2520rta_price_tag&env_type=pro&env_type_display=pro&db_name=rta_price_tag&type=mysql; aladdin_gray=; HWWAFSESTIME=1742212174397; HWWAFSESID=58c3d76a7e9f681a99; __token_="SEg6bW0jIzExOS42Ljk3LjM3IyNISDptbSMjMzFiNTIjIzNGRDJGMTdFMzA3OTBEMTU3MDA5NEY3NDAyNzUyQjRCRUU0NTZERTlDNUFGQzQyMDk4QTk0QTgxNEE2MUYwQkExQTZFNTkwMzc2RkIzOEUzMjZFODlEMUQzNDg2QzkyOTc5REFBNEI1NjVFQ0NFMjNFRTdBNjgxQUY2OTk4Mjk5RTgxQzgyMTk4M0M5MDk1MTFDOEZFM0IzQjE0MTM4RkY4MTRGNkI4QjdBMkNDMTM1RDZDRTgxRDdCMTQ2RkM4RkYxQUNFOURDRTQyRjYzQ0Y2QjBGQUMwOTM3Q0Y1NTMyRkNGRUMyRjNGRjNENDVCNjEwMEEyOTZENzA0NUQzNDQ="; rta-os_vender=3; venderId=3; dmall-locale=zh_HK',
        "Host": "newpricetag-partner.rta-os.com",
        "Origin": "https://partner.rta-os.com",
        "Referer": "https://partner.rta-os.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        # "graytoken": "gray"
    }
    # get_psid_from_displaydata(payment_display_data)
    # print(json.loads("null"))
    # with open("C:\\Users\\Administrator\\Downloads/S030.item_details_260220251006.i1", 'r') as f:
    #     for line in f.readlines():
    #         print(len(line.split("|")))
    # check_ip(headers)

    # num = sys.argv[1] if len(sys.argv)>1 else 10
    # pricetag_test(int(num))
    data = """
    
<!DOCTYPE html>

	

<html lang="zh-cn">
<head>
	   <meta charset="utf-8">
   <meta name="viewport" content="width=device-width, initial-scale=1">
   <title>HiFiNi - 音乐磁场</title>
      <meta name="keywords" content="HiFiNi,音乐磁场,歌曲下载网站" />
      <meta name="description" content="HiFiNi 是一个由音乐爱好者维护的分享平台, 旨在解决问题互帮互助, 如果您有需求, 请注册账号并发布信息、详细描述歌曲信息等, 我们会尽力帮您寻找

HiFiNi MUSIC BBS - HiFiNi.COM" />
   	<meta name="renderer" content="webkit">
	<meta http-equiv="X-UA-Compatible" content="IE=Edge,chrome=1" >
	<meta http-equiv="Cache-Control" content="no-transform"/>
	<meta http-equiv="Cache-Control" content="no-siteapp"/>
	<link rel="shortcut icon" href="view/img/favicon.ico" />
	<link rel="icon" sizes="32x32" href="view/img/favicon.ico">
    <link rel="Bookmark" href="view/img/favicon.ico" />
			<link rel="stylesheet" href="./plugin/jan/css/bootstrap-v2.css?1.0">
			<link rel="stylesheet" href="./plugin/jan/css/bootstrap-bbs-v2.css?1.0">
	<link rel="stylesheet" href="plugin/huux_notice/view/css/huux-notice.css" name="huux_notice">
	<!-- TAG Style -->
<link rel="stylesheet" href="plugin/git_tags/view/css/tag.css?1.0">
<style>
.haya-post-info-username.today .username {
	color: var(--danger) !important;
}
.haya-post-info-username.today .date {
	color: var(--danger) !important;
}
</style>
<link rel="stylesheet" href="./plugin/sg_sign_vip/css/sign.css">
<link rel="stylesheet" href="plugin/xn_paypal/view/css/jquery-labelauty.css">
</head>

<body>
	
	
	
	
	
	<style>.nav-link.buy:hover{color: red !important;}</style>
	<header class="navbar navbar-expand-lg navbar-dark bg-dark" id="header">
		<div class="container">
			<button class="navbar-toggler" type="button" data-toggle="collapse" data-target="#nav" aria-controls="navbar_collapse" aria-expanded="false" aria-label="展开菜单">
				<span class="navbar-toggler-icon"></span>
			</button>
			
			
			
			<a class="navbar-brand text-truncate" href="./">
				<img src="view/img/logo.png" class="logo-2">
							</a>
			
			
			
							<a class="navbar-brand hidden-lg" href="thread-create-0.htm" aria-label="发表主题"><i class="icon-edit icon"></i></a>
						
			
			
			<div class="collapse navbar-collapse" id="nav">
				<!-- 左侧：版块 -->
				<ul class="navbar-nav mr-auto">
					
					<li class="nav-item home" fid="0" data-active="fid-0"><a class="nav-link" href="."><i class="icon-home d-md-none"></i> 首页</a></li>
					
										
										
										
					<li class="nav-item " fid="1" data-active="fid-1">
						<a class="nav-link" href="forum-1.htm"><i class="icon-circle-o d-md-none"></i> 华语</a>
					</li>
										
										
										
										
					<li class="nav-item " fid="15" data-active="fid-15">
						<a class="nav-link" href="forum-15.htm"><i class="icon-circle-o d-md-none"></i> 日韩</a>
					</li>
										
										
										
										
					<li class="nav-item " fid="10" data-active="fid-10">
						<a class="nav-link" href="forum-10.htm"><i class="icon-circle-o d-md-none"></i> 欧美</a>
					</li>
										
										
										
										
					<li class="nav-item " fid="11" data-active="fid-11">
						<a class="nav-link" href="forum-11.htm"><i class="icon-circle-o d-md-none"></i> Remix</a>
					</li>
										
										
										
										
					<li class="nav-item " fid="12" data-active="fid-12">
						<a class="nav-link" href="forum-12.htm"><i class="icon-circle-o d-md-none"></i> 纯音乐</a>
					</li>
										
										
										
										
					<li class="nav-item " fid="13" data-active="fid-13">
						<a class="nav-link" href="forum-13.htm"><i class="icon-circle-o d-md-none"></i> 异次元</a>
					</li>
										
										
										
										
					<li class="nav-item zunshop" fid="17" data-active="fid-17">
						<a class="nav-link" href="forum-17.htm"><i class="icon-circle-o d-md-none"></i> 特供</a>
					</li>
										
										
										
										
					<li class="nav-item " fid="16" data-active="fid-16">
						<a class="nav-link" href="forum-16.htm"><i class="icon-circle-o d-md-none"></i> 茶馆</a>
					</li>
										
										
										
										
					<li class="nav-item " fid="18" data-active="fid-18">
						<a class="nav-link" href="forum-18.htm"><i class="icon-circle-o d-md-none"></i> 百科</a>
					</li>
										
										
										   <li class="nav-item">
						<a class="nav-link buy hidden-sm" href="my-pay.htm" style="color:#f57e42"><i class="icon-circle-o d-md-none"></i> 充值</a>
					</li>
										
										
					<li class="nav-item " fid="9" data-active="fid-9">
						<a class="nav-link" href="forum-9.htm"><i class="icon-circle-o d-md-none"></i> 站务</a>
					</li>
										
										
										
										
														</ul>
				<!-- 右侧：用户 -->
				<ul class="navbar-nav">
					<li class="nav-item hidden-lg">
	<a class="nav-link" href="search.htm"><i class="icon-search"></i> 搜索</a>
</li>	<li class="nav-item usernotice " id="nav-usernotice">
		<a class="nav-link" href="my-notice.htm"><i class="icon icon-bell"></i> 消息 <span class="d-none unread badge badge-danger badge-pill" id="nav-usernotice-unread-notices">0</span>			
		</a>
	</li>
	<li class="nav-item hidden-lg"><a class="nav-link" href="my-pay.htm"  ><i class="icon-shopping-cart"></i> 充值</a></li>
<li class="nav-item hidden-lg"><a class="nav-link" href="#" id="sg_sign_mobile" ><i class="icon-gift"></i> 签到</a></li>
									<li class="nav-item username"><a class="nav-link" href="my.htm"><img class="avatar-1" src="view/img/avatar.png"> panda62</a></li>
					<!-- 管理员 -->
										
					<li class="nav-item"><a class="nav-link" href="user-logout.htm"><i class="icon-sign-out"></i> 退出</a></li>
									
				</ul>
			</div>
		</div>
	</header>
	
	<main id="body">
		<div class="container">
	
		
<style>.thread .badge{display: none;} .t_icon {display: none;}.mt-3, .my-3{margin-top: 0.3rem !important;}.card.card-threadlist {margin-bottom: 1.3rem;}</style>
<div class="row">
	<div class="col-lg-9 main">
	
		
	
		<div class="card card-threadlist ">
			<div class="card-header">
				<ul class="nav nav-tabs card-header-tabs">
					<li class="nav-item">
						<a class="nav-link active" href="./index.htm">最新</a>
					</li>
										
					
					
					<li class="nav-item">
						<a class="nav-link " href="index-0-2.htm">热门</a>
					</li>
					<li class="nav-item">
						<a class="nav-link " href="index-0-3.htm">月榜</a>
					</li>
					<li class="nav-item">
						<a class="nav-link " href="index-0-4.htm">周榜</a>
					</li>
					<li class="nav-item">
						<a class="nav-link " href="index-0-5.htm">日榜</a>
					</li>
					<!--
					<li class="nav-item">
						<a class="nav-link " href="index-0-6.htm">新榜</a>
					</li>
						<li class="nav-item">
						<a class="nav-link " href="index-0-4.htm">周榜</a>
					</li>
					-->

				</ul>
			</div>
			<div class="card-body">
				<ul class="list-unstyled threadlist mb-0">
					
										
										
					
					
									
										  
					<li class="media thread tap top_3 " data-href="thread-6.htm" data-tid="6">
												
						<a href="user-1.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/000/1.png?1744344355">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																	<i class="icon-top-3"></i>
																								
																<a href="thread-6.htm" target="_blank"><span style=color:#007ef7;> 积分 / VIP 使用问题说明, 砥砺前行, 不忘初心</span></a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-9.htm" ><span class="board-bg" style="border-radius: 2px;background-color: #f1c84c;width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>站务</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="1">Admin</span>
									<span class="date text-grey hidden-sm">2018-12-10</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="2176794">小亦俊</span>
										<span class="text-grey">13小时前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>1887050</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">4986</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.1</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap top_3 " data-href="thread-1575.htm" data-tid="1575">
												
						<a href="user-1.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/000/1.png?1744344355">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																	<i class="icon-top-3"></i>
																								
																<a href="thread-1575.htm" target="_blank"><span style=color:#0e990b;>新人快速上手、相关功能使用说明</span></a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-9.htm" ><span class="board-bg" style="border-radius: 2px;background-color: #f1c84c;width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>站务</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="1">Admin</span>
									<span class="date text-grey hidden-sm">2019-1-28</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="4810288">190866858</span>
										<span class="text-grey">9小时前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>1560737</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">23878</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.2</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap top_3 " data-href="thread-16216.htm" data-tid="16216">
												
						<a href="user-1.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/000/1.png?1744344355">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																	<i class="icon-top-3"></i>
																								
																<a href="thread-16216.htm" target="_blank"><span style=color:#007ef7;>链接失效/上传错误等资源问题在这里处理</span></a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-9.htm" ><span class="board-bg" style="border-radius: 2px;background-color: #f1c84c;width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>站务</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="1">Admin</span>
									<span class="date text-grey hidden-sm">2019-6-13</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="304810">6536</span>
										<span class="text-grey">8小时前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>836869</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">7365</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.3</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap  " data-href="thread-83333.htm" data-tid="83333">
												
						<a href="user-2006.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/000/2006.png?1554012822">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-83333.htm" target="_blank">阿YueYue/戾格《沈园外》[FLAC/MP3-320K]</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-1.htm" ><span class="board-bg" style="border-radius: 2px;background-color: #F21120;width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>华语</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="2006">隔壁老王</span>
									<span class="date text-grey hidden-sm">2020-12-31</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="1026548">VZERO000</span>
										<span class="text-grey">1秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>114423</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">13779</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.4</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap  " data-href="thread-129913.htm" data-tid="129913">
												
						<a href="user-17923.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/000/17923.png?1568987634">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-129913.htm" target="_blank">张蔷《相思好比小蚂蚁》[FLAC/MP3-320K]</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-1.htm" ><span class="board-bg" style="border-radius: 2px;background-color: #F21120;width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>华语</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="17923">tudou</span>
									<span class="date text-grey hidden-sm">2021-8-24</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="1144652">西门干金莲</span>
										<span class="text-grey">2秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>1700</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">95</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.5</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap zun  " data-href="thread-411028.htm" data-tid="411028">
												
						<a href="user-2105095.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/002/2105095.png?1660499491">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-411028.htm" target="_blank">兔裹煎蛋卷《人间自在仙》[FLAC/MP3-320K]</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-17.htm" ><span class="board-bg" style="border-radius: 2px;background-image: linear-gradient(0deg, #0e9955, #0e9955);width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>特供</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="2105095"><i class="icon-diamond" aria-hidden="true" style="color:Red;" title="VIP"></i><span style="color:red;">晓風丶殘月</span></span>
									<span class="date text-grey hidden-sm">8月前</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="373501">x05330</span>
										<span class="text-grey">5秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>256</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">40</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.6</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap zun  " data-href="thread-428640.htm" data-tid="428640">
												
						<a href="user-4251468.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/004/4251468.png?1726887910">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-428640.htm" target="_blank">en《爱错》[FLAC/MP3-320K]</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-17.htm" ><span class="board-bg" style="border-radius: 2px;background-image: linear-gradient(0deg, #0e9955, #0e9955);width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>特供</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="4251468"><i class="icon-diamond" aria-hidden="true" style="color:Red;" title="VIP"></i><span style="color:red;">abcd2321</span></span>
									<span class="date text-grey hidden-sm">6月前</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="1051973">lansetk000</span>
										<span class="text-grey">5秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>4235</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">588</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.7</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap zun  " data-href="thread-319816.htm" data-tid="319816">
												
						<a href="user-745046.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="view/img/avatar.png">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-319816.htm" target="_blank">赵雷  专辑《赵小雷》 （十二首）   含《画》、《南方姑娘》、《妈妈》、《民谣》等 分轨 [FLAC / MP3]</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-17.htm" ><span class="board-bg" style="border-radius: 2px;background-image: linear-gradient(0deg, #0e9955, #0e9955);width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>特供</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="745046"><i class="icon-diamond" aria-hidden="true" style="color:Red;" title="VIP"></i><span style="color:red;">dagezi</span></span>
									<span class="date text-grey hidden-sm">2023-9-16</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="4656191">hifiLM</span>
										<span class="text-grey">9秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>2711</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">432</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.8</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap zun  " data-href="thread-308470.htm" data-tid="308470">
												
						<a href="user-2546618.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/002/2546618.png?1744085850">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-308470.htm" target="_blank">GAI周延/戴佩妮 - 《用情 (Live)》[FLAC/MP3-128K]</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-17.htm" ><span class="board-bg" style="border-radius: 2px;background-image: linear-gradient(0deg, #0e9955, #0e9955);width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>特供</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="2546618">bandrocks</span>
									<span class="date text-grey hidden-sm">2023-8-7</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="4041254">jrzling1</span>
										<span class="text-grey">12秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>24247</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">4303</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.9</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap  " data-href="thread-2017.htm" data-tid="2017">
												
						<a href="user-3.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/000/3.png?1544533319">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-2017.htm" target="_blank">阿杜《他一定很爱你》[FLAC/MP3-320K]</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-1.htm" ><span class="board-bg" style="border-radius: 2px;background-color: #F21120;width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>华语</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="3">胖虎</span>
									<span class="date text-grey hidden-sm">2019-2-5</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="1300460">e7chuah</span>
										<span class="text-grey">12秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>77876</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">9946</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.10</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap  " data-href="thread-22149.htm" data-tid="22149">
												
						<a href="user-17923.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/000/17923.png?1568987634">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-22149.htm" target="_blank">周慧敏《自作多情》[FLAC/MP3-320K]</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-1.htm" ><span class="board-bg" style="border-radius: 2px;background-color: #F21120;width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>华语</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="17923">tudou</span>
									<span class="date text-grey hidden-sm">2019-8-25</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="1545874">st957476040</span>
										<span class="text-grey">15秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>36998</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">4406</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.11</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap  " data-href="thread-492207.htm" data-tid="492207">
												
						<a href="user-4674137.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/004/4674137.png?1743729945">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-492207.htm" target="_blank">AiScReam《愛♡スクリ～ム!》[FLAC/MP3-320K]</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-15.htm" ><span class="board-bg" style="border-radius: 2px;background-color: #53BEF1;width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>日韩</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="4674137">kaixinshu606</span>
									<span class="date text-grey hidden-sm">8天前</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="4560669">DWPH</span>
										<span class="text-grey">15秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>285</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">39</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.12</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap  " data-href="thread-80898.htm" data-tid="80898">
												
						<a href="user-17923.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/000/17923.png?1568987634">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-80898.htm" target="_blank">卓文萱/曹格《梁山伯与茱丽叶》[FLAC/MP3-320K]</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-1.htm" ><span class="board-bg" style="border-radius: 2px;background-color: #F21120;width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>华语</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="17923">tudou</span>
									<span class="date text-grey hidden-sm">2020-12-18</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="4049329">mauses</span>
										<span class="text-grey">17秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>29338</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">3675</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.13</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap  " data-href="thread-354574.htm" data-tid="354574">
												
						<a href="user-17923.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/000/17923.png?1568987634">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-354574.htm" target="_blank">刘烨溦《没本事忘记》[FLAC/MP3-320K]</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-1.htm" ><span class="board-bg" style="border-radius: 2px;background-color: #F21120;width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>华语</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="17923">tudou</span>
									<span class="date text-grey hidden-sm">2024-1-13</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="4405095">wenning1997</span>
										<span class="text-grey">18秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>688</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">87</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.14</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap zun  " data-href="thread-481870.htm" data-tid="481870">
												
						<a href="user-3538387.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/003/3538387.png?1735089915">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-481870.htm" target="_blank">林志炫《没离开过》[Hi-Res FLAC]</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-17.htm" ><span class="board-bg" style="border-radius: 2px;background-image: linear-gradient(0deg, #0e9955, #0e9955);width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>特供</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="3538387">普通牛马</span>
									<span class="date text-grey hidden-sm">1月前</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="509230">r459202667</span>
										<span class="text-grey">22秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>322</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">62</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.15</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap  " data-href="thread-66654.htm" data-tid="66654">
												
						<a href="user-17923.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/000/17923.png?1568987634">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-66654.htm" target="_blank">一杯陈豆浆《漫步人生路》[FLAC/MP3-320K]</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-1.htm" ><span class="board-bg" style="border-radius: 2px;background-color: #F21120;width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>华语</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="17923">tudou</span>
									<span class="date text-grey hidden-sm">2020-9-23</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="2212642">caiyusong</span>
										<span class="text-grey">24秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>54776</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">4989</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.16</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap  " data-href="thread-495302.htm" data-tid="495302">
												
						<a href="user-2006.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/000/2006.png?1554012822">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-495302.htm" target="_blank">黄霄雲《若难过何必要过》[FLAC/MP3-320K]</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username today">

 
 <a  style="color:#748594;" href="forum-1.htm" ><span class="board-bg" style="border-radius: 2px;background-color: #F21120;width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>华语</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="2006">隔壁老王</span>
									<span class="date text-grey hidden-sm">4小时前</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="551375">ccnmg</span>
										<span class="text-grey">25秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>85</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">9</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.17</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap  " data-href="thread-4461.htm" data-tid="4461">
												
						<a href="user-17923.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/000/17923.png?1568987634">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-4461.htm" target="_blank">F.I.R.飞儿乐团《我们的爱》[FLAC/MP3-320K]</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-1.htm" ><span class="board-bg" style="border-radius: 2px;background-color: #F21120;width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>华语</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="17923">tudou</span>
									<span class="date text-grey hidden-sm">2019-3-13</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="1300460">e7chuah</span>
										<span class="text-grey">32秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>245953</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">25422</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.18</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap zun  " data-href="thread-488796.htm" data-tid="488796">
												
						<a href="user-4482594.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/004/4482594.png?1735047321">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-488796.htm" target="_blank">苡纯《西楼儿女（含加长版）》［FLAC/MP3-320k］</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-17.htm" ><span class="board-bg" style="border-radius: 2px;background-image: linear-gradient(0deg, #0e9955, #0e9955);width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>特供</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="4482594"><i class="icon-diamond" aria-hidden="true" style="color:Red;" title="VIP"></i><span style="color:red;">蚂蚁呀嘿啊</span></span>
									<span class="date text-grey hidden-sm">18天前</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="4332036">1okm</span>
										<span class="text-grey">32秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>1759</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">249</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.19</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap  " data-href="thread-11734.htm" data-tid="11734">
												
						<a href="user-27558.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/000/27558.png?1581956983">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-11734.htm" target="_blank">降央卓玛《走天涯》[FLAC/MP3-320K]</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-1.htm" ><span class="board-bg" style="border-radius: 2px;background-color: #F21120;width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>华语</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="27558">花荣</span>
									<span class="date text-grey hidden-sm">2019-4-8</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="2208521">936815556</span>
										<span class="text-grey">35秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>44989</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">4209</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.20</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap  " data-href="thread-85096.htm" data-tid="85096">
												
						<a href="user-2006.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/000/2006.png?1554012822">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-85096.htm" target="_blank">滨崎步《YOU》[FLAC/MP3-320K]</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-15.htm" ><span class="board-bg" style="border-radius: 2px;background-color: #53BEF1;width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>日韩</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="2006">隔壁老王</span>
									<span class="date text-grey hidden-sm">2021-1-10</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="3471952">fishstand</span>
										<span class="text-grey">36秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>2995</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">179</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.21</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap zun  " data-href="thread-478657.htm" data-tid="478657">
												
						<a href="user-4608008.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/004/4608008.png?1734099008">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-478657.htm" target="_blank">2727厂牌&EINK&FEEEleven&DANNY K&JYnostop&周夏影&Buzzy&鼠尾草《Cy2Ph72Er7》(2727 Cypher)[FLAC/MP3-320K]</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-17.htm" ><span class="board-bg" style="border-radius: 2px;background-image: linear-gradient(0deg, #0e9955, #0e9955);width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>特供</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="4608008"><i class="icon-diamond" aria-hidden="true" style="color:Red;" title="VIP"></i><span style="color:red;">TracySky</span></span>
									<span class="date text-grey hidden-sm">1月前</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="3458342">pupuk789</span>
										<span class="text-grey">42秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>151</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">28</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.22</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap  " data-href="thread-2524.htm" data-tid="2524">
												
						<a href="user-5.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/000/5.png?1564502593">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-2524.htm" target="_blank">SHE《恋人未满》[FLAC/MP3-320K]</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-1.htm" ><span class="board-bg" style="border-radius: 2px;background-color: #F21120;width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>华语</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="5">Pain</span>
									<span class="date text-grey hidden-sm">2019-2-16</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="1300460">e7chuah</span>
										<span class="text-grey">44秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>77708</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">7976</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.23</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
													
										  
					<li class="media thread tap  " data-href="thread-276772.htm" data-tid="276772">
												
						<a href="user-2006.htm" tabindex="-1" class="ml-1 mt-1 mr-3">
							<img class="avatar-3" src="upload/avatar/000/2006.png?1554012822">
						</a>
						
					
						<div class="media-body">
							<div class="subject break-all">
							
								
																								
																<a href="thread-276772.htm" target="_blank">JORDANN《Dehors》[FLAC/MP3-320K]</a>
								
								
								
																								
								
																								
							</div>
							<div class="d-flex justify-content-between small mt-1">
								<div>
								
								 									
<span class="haya-post-info-username ">

 
 <a  style="color:#748594;" href="forum-10.htm" ><span class="board-bg" style="border-radius: 2px;background-color: #BE5281;width: 0.64rem;height: 0.64rem;display: inline-block;margin-right: 5px;"></span>欧美</a>
 
 <span class="koox-g  hidden-sm "> • </span>
 
 



									<span class="username text-grey mr-1   hidden-sm" uid="2006">隔壁老王</span>
									<span class="date text-grey hidden-sm">2023-4-21</span>
									</span>

									
																											
																		<span>
										<span class="text-grey mx-2">←</span>
										<span class="username text-grey mr-1 " uid="3616256">arsfans</span>
										<span class="text-grey">44秒前</span>
									</span>
																											 
								</div>
								<div class="text-muted small">
									
							 
									
																		     <span class="eye comment-o ml-2 hidden-sm d-none"><i class="jan-icon-fire-1"></i>41513</span>
									
									
									
									
									<span class="reply comment-o ml-2 ">5662</span>
									<span class="rank comment-o ml-2 hidden-sm d-none"><i class="jan-icon-crown"></i>No.24</span>
											
								</div>
							</div>
						</div>
					</li>
					<div class="jan-hr"></div>
																			
				</ul>
			</div>
		</div>
		
				
		<nav class="my-3"><ul class="pagination justify-content-center flex-wrap"><li class="page-item active"><a href="index-1.htm" class="page-link">1</a></li><li class="page-item"><a href="index-2.htm" class="page-link">2</a></li><li class="page-item"><a href="index-3.htm" class="page-link">3</a></li><li class="page-item"><a href="index-4.htm" class="page-link">4</a></li><li class="page-item"><a href="index-5.htm" class="page-link">5</a></li><li class="page-item"><a href="index-6.htm" class="page-link">6</a></li><li class="page-item"><a href="index-7.htm" class="page-link">7</a></li><li class="page-item"><a href="index-8.htm" class="page-link">8</a></li><li class="page-item"><a href="index-9.htm" class="page-link">9</a></li><li class="page-item"><a href="index-10.htm" class="page-link">10</a></li><li class="page-item"><a href="index-15974.htm" class="page-link">...15974</a></li><li class="page-item"><a href="index-2.htm" class="page-link">▶</a></li></ul></nav>
		
	</div>
	<div class="col-lg-3 d-none d-lg-block aside">
		<a role="button" class="btn btn-primary btn-block mb-3" href="thread-create-0.htm">发新帖</a>
		<div class="mibbs_con card" id="start">
    <span id="sg_sign" class="mibbs_signpanel JD_sign ">
        <div class="font" id="sign"></div>
        <div class="fblock">
            <div class="all" id="peo"></div>
            <div class="line">
                <span style="font-size:12px;" id="day"></span>
            </div>
        </div>
    </span>

</div>
		<div class="card card-site-info">
			
			<div class="m-3">
				<div class="small line-height-3">HiFiNi 是一个由音乐爱好者维护的分享平台, 旨在解决问题互帮互助, 如果您有需求, 请注册账号并发布信息、详细描述歌曲信息等, 我们会尽力帮您寻找
<br>
HiFiNi MUSIC BBS - HiFiNi.COM</div>
			</div>
				<div class="card-footer p-2">
				<table class="w-100 small">
					<tr align="center">
						<td>
							<span class="text-muted">主题数</span><br>
							<b>370314</b>
						</td>
						<td>
							<span class="text-muted">帖子数</span><br>
							<b>59917378</b>
						</td>
						<td>
							<span class="text-muted">用户数</span><br>
							<b>********</b>
						</td>

					</tr>
				</table>
			</div>
			
		</div>
		


<div class="form-group">
  <form action="search.htm" id="search_form">
      <div class="input-group">
        <input type="text" class="form-control" placeholder="关键词" name="keyword">
        <div class="input-group-append">
          <button class="btn btn-primary" type="submit">搜索</button>
        </div>
      </div>
  </form>
</div>
<!-- 主页右侧 -->
 <div class="card">
	<div class="card-header">热门节点</div>
<div id="taghot">
	<ul>
				  
		      <li><a href='tag-38819.htm'>HiRes经典老歌</a></li>
		  				  
		      <li><a href='tag-30936.htm'>80后回忆</a></li>
		  				  
		      <li><a href='tag-260.htm'>刘德华</a></li>
		  				  
		      <li><a href='tag-254.htm'>陈奕迅</a></li>
		  				  
		      <li><a href='tag-350.htm'>周深</a></li>
		  				  
		      <li><a href='tag-362.htm'>周杰伦</a></li>
		  				  
		      <li><a href='tag-22382.htm'>洋澜一</a></li>
		  				  
		      <li><a href='tag-352.htm'>张学友</a></li>
		  				  
		      <li><a href='tag-2192.htm'>Taylor Swift</a></li>
		  				  
		      <li><a href='tag-6113.htm'>flac</a></li>
		  				  
		      <li><a href='tag-176.htm'>林俊杰</a></li>
		  				  
		      <li><a href='tag-1991.htm'>李玟</a></li>
		  				  
		      <li><a href='tag-4183.htm'>半吨兄弟</a></li>
		  				  
		      <li><a href='tag-272.htm'>汪苏泷</a></li>
		  				  
		      <li><a href='tag-95.htm'>张杰</a></li>
		  				  
		      <li><a href='tag-253.htm'>王菲</a></li>
		  				  
		      <li><a href='tag-1381.htm'>谭咏麟</a></li>
		  				  
		      <li><a href='tag-14603.htm'>苏星婕</a></li>
		  				  
		      <li><a href='tag-1184.htm'>季彦霖</a></li>
		  				  
		      <li><a href='tag-113.htm'>毛不易</a></li>
		  				  
		      <li><a href='tag-705.htm'>容祖儿</a></li>
		  				  
		      <li><a href='tag-315.htm'>Beyond</a></li>
		  				  
		      <li><a href='tag-2793.htm'>黎明</a></li>
		  				  
		      <li><a href='tag-348.htm'>张敬轩</a></li>
		  				  
		      <li><a href='tag-701.htm'>王杰</a></li>
		  				  
		      <li><a href='tag-2064.htm'>古巨基</a></li>
		  				  
		      <li><a href='tag-1051.htm'>郁可唯</a></li>
		  				  
		      <li><a href='tag-531.htm'>洛天依</a></li>
		  				  
		      <li><a href='tag-566.htm'>王心凌</a></li>
		  				  
		      <li><a href='tag-632.htm'>胡彦斌</a></li>
		  				  
		      <li><a href='tag-584.htm'>张国荣</a></li>
		  				  
		      <li><a href='tag-166.htm'>许嵩</a></li>
		  				  
		      <li><a href='tag-800.htm'>陈楚生</a></li>
		  				  
		      <li><a href='tag-400.htm'>夏婉安</a></li>
		  				  
		      <li><a href='tag-284.htm'>张靓颖</a></li>
		  				  
		      <li><a href='tag-751.htm'>梁静茹</a></li>
		  				  
		      <li><a href='tag-4823.htm'>郭富城</a></li>
		  				  
		      <li><a href='tag-1992.htm'>任贤齐</a></li>
		  				  
		      <li><a href='tag-901.htm'>五月天</a></li>
		  				  
		      <li><a href='tag-1296.htm'>杨千嬅</a></li>
		  				  
		      <li><a href='tag-462.htm'>郑秀文</a></li>
		  				  
		      <li><a href='tag-470.htm'>双笙</a></li>
		  				  
		      <li><a href='tag-950.htm'>孙燕姿</a></li>
		  				  
		      <li><a href='tag-30.htm'>邓紫棋</a></li>
		  				  
		      <li><a href='tag-7262.htm'>Yanni</a></li>
		  				  
		      <li><a href='tag-17210.htm'>怪阿姨</a></li>
		  				  
		      <li><a href='tag-197.htm'>周华健</a></li>
		  				  
		      <li><a href='tag-532.htm'>胡夏</a></li>
		  				  
		      <li><a href='tag-203.htm'>李克勤</a></li>
		  				  
		      <li><a href='tag-347.htm'>谭维维</a></li>
		  				  
		      <li><a href='tag-3185.htm'>黄静美</a></li>
		  				  
		      <li><a href='tag-592.htm'>任然</a></li>
		  				  
		      <li><a href='tag-199.htm'>音阙诗听</a></li>
		  				  
		      <li><a href='tag-537.htm'>孙露</a></li>
		  				  
		      <li><a href='tag-320.htm'>张信哲</a></li>
		  				  
		      <li><a href='tag-1870.htm'>王力宏</a></li>
		  				  
		      <li><a href='tag-1489.htm'>张惠妹</a></li>
		  				  
		      <li><a href='tag-63.htm'>林忆莲</a></li>
		  				  
		      <li><a href='tag-627.htm'>魏佳艺</a></li>
		  				  
		      <li><a href='tag-251.htm'>银临</a></li>
		  				  
		      <li><a href='tag-5585.htm'>刘宇宁</a></li>
		  				  
		      <li><a href='tag-548.htm'>谢霆锋</a></li>
		  				  
		      <li><a href='tag-490.htm'>封茗囧菌</a></li>
		  				  
		      <li><a href='tag-359.htm'>张韶涵</a></li>
		  				  
		      <li><a href='tag-72.htm'>薛之谦</a></li>
		  				  
		      <li><a href='tag-796.htm'>蔡依林</a></li>
		  				  
		      <li><a href='tag-288.htm'>汪峰</a></li>
		  				  
		      <li><a href='tag-217.htm'>方大同</a></li>
		  				  
		      <li><a href='tag-368.htm'>花僮</a></li>
		  				  
		      <li><a href='tag-5169.htm'>赵乃吉</a></li>
		  				  
		      <li><a href='tag-213.htm'>河图</a></li>
		  				  
		      <li><a href='tag-628.htm'>周传雄</a></li>
		  				  
		      <li><a href='tag-96.htm'>张碧晨</a></li>
		  				  
		      <li><a href='tag-145.htm'>海来阿木</a></li>
		  				  
		      <li><a href='tag-795.htm'>陶喆</a></li>
		  				  
		      <li><a href='tag-5862.htm'>任夏</a></li>
		  				  
		      <li><a href='tag-14588.htm'>尹昔眠</a></li>
		  				  
		      <li><a href='tag-1993.htm'>林子祥</a></li>
		  				  
		      <li><a href='tag-8378.htm'>天赐的声音</a></li>
		  				  
		      <li><a href='tag-413.htm'>刘惜君</a></li>
		  				  
		      <li><a href='tag-238.htm'>房东的猫</a></li>
		  			</ul>
</div>
</div>		
		<div class="card friendlink">
			<div class="card-header">友情链接</div>
			<div class="card-body small">
				<ul>
										<li class="mb-1 line-height-2">
						<a href="https://tv.cctv.com/lm/dzw/index.shtml?spm=C28340.PbtJD1QH3ct0.E" target="_blank">
							CCTV-1 等着我						</a>
					</li>
										<li class="mb-1 line-height-2">
						<a href="https://www.hifini.com" target="_blank">
							Internet						</a>
					</li>
									</ul>
			</div>
		</div>
		
	

	</div>
</div>


				
			
		
				
		</div>
	</main>
	
	
	
	<footer class="text-muted small bg-dark py-4 mt-3" id="footer">
	<div class="container">
		<div class="row">
			<div class="col">2018 ☯ <a href="./" target="_blank" class="text-muted" title="[官网] HiFiNi-音乐磁场"><b>HiFiNi.COM</b></a>
				
			</div>
			<div class="col text-right" style="font-family: hifini2018,jan;font-size: 0.9rem;">
				
				PROCESSED: <b>0.303</b>
				
			</div>
		</div>
	</div>
</footer>
<style>@media (max-width:576px){.col-lg-3.msign{padding:0 0.5rem 0 0.5rem !important;}}@media (min-width:768px){.container{padding-left:0;}}@media (min-width:576px){.container{padding-left:0;}.col-lg-3.msign{padding-left:1rem !important;}}@media (min-width:992px){.col-lg-3.msign{padding-left:0rem !important;}}@media (max-width:576px){#body > .container > .row > div{padding-bottom:0 !important;}}</style>
	
	
	
	<!--[if ltg IE 9]>
	<script>window.location = 'browser.htm';</script>
	<![endif]-->
	
	
	
			<script src="lang/zh-cn/bbs.js?1.0"></script>
	<script src="view/js/jquery-3.1.0.js?1.0"></script>
	<script src="view/js/popper.js?1.0"></script>
	<script src="view/js/bootstrap.js?1.0"></script>
	<script src="view/js/xiuno.js?1.0"></script>
	<script src="view/js/bootstrap-plugin.js?1.0"></script>
	<script src="view/js/async.js?1.0"></script>
	<script src="view/js/form.js?1.0"></script>
	<script>
	var debug = DEBUG = 0;
	var url_rewrite_on = 1;
	var forumarr = {
    "1": "华语",
    "15": "日韩",
    "10": "欧美",
    "11": "Remix",
    "12": "纯音乐",
    "13": "异次元",
    "17": "特供",
    "16": "茶馆",
    "18": "百科",
    "9": "站务",
    "19": "归墟"
};
	var fid = 0;
	var uid = 4046068;
	var gid = 101;
	xn.options.water_image_url = 'view/img/water-small.png';	// 水印图片 / watermark image
	</script>
	<script src="view/js/bbs.js?1.0"></script>
	<script>
// 版主管理：高亮
$('.mod-button button.sg_highlight').on('click', function() {
	var modtid = $('input[name="modtid"]').checked();
	if(modtid.length == 0) return $.alert(lang.please_choose_thread);
	var radios = xn.form_radio('sg_highlight', {"0": "取消高亮", "1": "<span style=\"color:#ff0000;\">高亮一</span>","2": "<span style=\"color:#0e990b;\">高亮二</span>", "3": "<span style=\"color:#007ef7;\">高亮三</span>", "4": "<span style=\"color:#f900ff;\">高亮四</span>", "5": "<span style=\"color:#fff000;\">高亮五</span>"});
	$.confirm("设置主题为高亮", function() {
		var tids = xn.implode('_', modtid);
		var sg_highlight = $('input[name="sg_highlight"]').checked();
		var postdata = {sg_highlight: sg_highlight};
		$.xpost(xn.url('mod-sg_highlight-'+tids), postdata, function(code, message) {
			if(code != 0) return $.alert(message);
			$.alert(message).delay(1000).location('');
		});
	}, {'body': '<p>选择高亮：'+radios+'</p>'});
})
</script>

<script src="plugin/tt_credits/view/js/tt_credits.js?1.0"></script>
</body>

</html>

<link rel="stylesheet" href="plugin/hifini_footer/css/scroll.css">

<div id="scroll_to_list" style="position: fixed; _position: absolute; bottom: 320px; right: 10px; width: 70px; height: 70px;">
        
					
        		<a href="thread-create-0.htm" class="mui-rightlist hidden-sm hidden-md" title="发新帖"><span><i class="icon-pencil"></i></span></a>
			<a href="search.htm" class="mui-rightlist"  title="搜索"><span><i class="icon-search"></i></span></a>
	    <a id="scroll_to_top" href="javascript:void(0);"  class="mui-rightlist"  title="返回顶部"><i class="icon-angle-double-up"></i></a>




</div>

<script>


var sg_sign_mobile = $('#sg_sign_mobile');
$('#sg_sign_mobile,#sg_sign,#xn_sign').click(function () {
		
    var sign = "18595cad92952ec7d24e10d4cd586461ea2d475c43eff741e0a3ce3333ea2f54";

	$.xpost(xn.url('sg_sign'), {'sign':  sign}, function(code, message) {
			$.alert(message);
			sg_sign_mobile.delay(1500).location(xn.url('sg_sign'));
	});
	return false;
});





var jscroll_to_top = $('#scroll_to_top');
$(window).scroll(function() {
	if ($(window).scrollTop() >= 500) {
	   jscroll_to_top.fadeIn(300);
	} else {
		jscroll_to_top.fadeOut(300);
	}
});

jscroll_to_top.on('click', function() {
	$('html,body').animate({scrollTop: '0px' }, 100);
});
</script>


<script>
$('li[data-active="fid-0"]').addClass('active');
</script>
<script>
jsearch_form = $('#search_form');
jsearch_form.on('submit', function() {
	var keyword = jsearch_form.find('input[name="keyword"]').val();
	var url = xn.url('search-'+xn.urlencode(keyword));
	window.location = url;
	return false;
});
</script>
<script>
var sg_sign = $('#sg_sign');
var sign = $('#sign');
var peo = $('#peo');
var day = $('#day');
var s1 = '已签'; 
var s2 = '<i class="jan-icon-users-1"></i>1376405人'; 
var s3 = '<i class="jan-icon-chart-bar-4"></i> 连续签到 1 天'; 
var sign = sign.html(s1);
var peo = peo.html(s2);
var day = day.html(s3);
</script>

     """
    res = re.search("var\s+sign\s=\s\"(\S+)\"", data)
    print(res.groups())
