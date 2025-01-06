import json
import datetime

import jmespath
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

def get_pro_desc(record):
    if "${itemIpf}" in ("STOCKOUT", "NORMAL"):
        return ""
    return str(jmespath.search("promotions[*].proSloganMap.en_US | [0]", record) or "")


def get_rptype(record):
    rptype = jmespath.search("ware.sapExtVO.extendInfo.rpType", record)
    rptype_map = {"0": "AO",
                  "1": "SGO",
                  "2": "MO",
                  "9": "ND"}
    return rptype_map.get(rptype, "")


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
    " 19 0 ": jmespath.search("extraDataInfo.supplierCode", record) or "",
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




if __name__ == "__main__":
    pass