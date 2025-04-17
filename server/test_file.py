import json
import datetime
import logging
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


<<<<<<< Updated upstream
if __name__ == "__main__":
    # print(json.dumps(gen_map(), indent=4, ensure_ascii=False))
    # print(json.dumps(current_map, indent=4, ensure_ascii=False))
    print(len("29300650371938|5120209|PHILADELPHIA CREAM CHEESE 226G|PHILADELPHIA|30104|3010401|1 EA|EA|1.000| |Y|||||0|660||||||||||||||MO||0|NORMAL".split("|")))
=======
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

    num = sys.argv[1] if len(sys.argv)>1 else 10
    pricetag_test(int(num))
>>>>>>> Stashed changes
