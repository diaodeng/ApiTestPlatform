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
    data = """
INSERT INTO sys_menu VALUES (1061,"测试管理",0,1,"hrm",null,null,1,0,"M","0","0",null,"component","admin","2024-05-06 10:07:50","admin","2024-11-06 15:27:10","");
INSERT INTO sys_menu VALUES (1062,"项目管理",1061,1,"project","hrm/project/index",null,1,0,"M","0","0","hrm:project:list","clipboard","admin","2024-05-06 10:07:50","admin","2024-05-06 10:24:34","");
INSERT INTO sys_menu VALUES (1063,"项目列表",1062,1,"project","hrm/project/index",null,1,0,"C","0","0","hrm:project:list","clipboard","admin","2024-05-06 10:07:50","admin","2024-05-06 10:07:50","");
INSERT INTO sys_menu VALUES (1064,"DebugTalk.py",1062,2,"debugtalk","hrm/debugtalk/index",null,1,0,"C","0","0","hrm:debugtalk:list","code","admin","2024-05-06 10:07:50","admin","2024-09-02 10:59:27","");
INSERT INTO sys_menu VALUES (1065,"模块管理",1061,2,"module","hrm/module/index",null,1,0,"C","0","0","hrm:module:list","example","admin","2024-05-06 10:07:50","admin","2024-05-06 10:07:50","");
INSERT INTO sys_menu VALUES (1066,"用例管理",1061,4,"case","hrm/case/index",null,1,0,"C","0","0","hrm:case:list","size","admin","2024-05-06 10:07:50","admin","2024-10-10 19:41:13","");
INSERT INTO sys_menu VALUES (1067,"配置管理",1061,3,"config","hrm/config/index",null,1,0,"C","0","0","hrm:config:list","system","admin","2024-05-06 10:07:50","admin","2024-10-10 19:41:19","");
INSERT INTO sys_menu VALUES (1068,"测试计划",1061,5,"qtr","",null,1,0,"M","0","0","","skill","admin","2024-05-06 10:07:50","admin","2024-08-25 13:33:19","");
INSERT INTO sys_menu VALUES (1069,"报告管理",1061,6,"report","hrm/report/index",null,1,0,"C","0","0","hrm:report:list","redis-list","admin","2024-05-06 10:07:50","admin","2024-05-06 10:07:50","");
INSERT INTO sys_menu VALUES (1070,"环境管理",1153,1,"env","hrm/env/index",null,1,0,"C","0","0","hrm:env:list","textarea","admin","2024-05-06 10:07:50","admin","2024-10-24 19:45:10","");
INSERT INTO sys_menu VALUES (1071,"新增",1066,0,"",null,null,1,0,"F","0","0","hrm:case:add","#","admin","2024-05-09 10:06:11","admin","2024-05-09 10:06:11","");
INSERT INTO sys_menu VALUES (1072,"修改-确定",1066,1,"",null,null,1,0,"F","0","0","hrm:case:edit","#","admin","2024-05-09 10:16:59","admin","2024-05-09 12:53:52","");
INSERT INTO sys_menu VALUES (1073,"删除",1066,2,"",null,null,1,0,"F","0","0","hrm:case:remove","#","admin","2024-05-09 10:16:59","admin","2024-05-09 10:16:59","");
INSERT INTO sys_menu VALUES (1074,"导出",1066,3,"",null,null,1,0,"F","0","0","hrm:case:export","#","admin","2024-05-09 10:16:59","admin","2024-05-09 10:16:59","");
INSERT INTO sys_menu VALUES (1075,"修改-查看详情",1066,4,"",null,null,1,0,"F","0","0","hrm:case:detail","#","admin","2024-05-09 12:53:32","admin","2024-05-09 12:53:32","");
INSERT INTO sys_menu VALUES (1076,"修改",1065,0,"",null,null,1,0,"F","0","0","hrm:module:edit","#","admin","2024-05-09 12:53:32","admin","2024-05-09 12:53:32","");
INSERT INTO sys_menu VALUES (1077,"删除",1065,1,"",null,null,1,0,"F","0","0","hrm:module:remove","#","admin","2024-05-09 12:53:32","admin","2024-05-09 12:53:32","");
INSERT INTO sys_menu VALUES (1078,"导出",1065,2,"",null,null,1,0,"F","0","0","hrm:module:export","#","admin","2024-05-09 12:53:32","admin","2024-05-09 12:53:32","");
INSERT INTO sys_menu VALUES (1079,"新增",1065,3,"",null,null,1,0,"F","0","0","hrm:module:add","#","admin","2024-05-09 12:53:32","admin","2024-05-09 12:53:32","");
INSERT INTO sys_menu VALUES (1080,"查看详情",1065,4,"",null,null,1,0,"F","0","0","hrm:module:detail","#","admin","2024-05-09 12:53:32","admin","2024-05-09 12:53:32","");
INSERT INTO sys_menu VALUES (1081,"接口管理",1061,8,"api","hrm/api/index",null,1,0,"C","0","0","hrm:api:tree","icon","admin","2024-06-13 14:24:42","admin","2024-09-18 15:45:38","");
INSERT INTO sys_menu VALUES (1083,"用例调试",1066,5,"",null,null,1,0,"F","0","0","hrm:case:debug","#","admin","2024-07-20 17:54:39","admin","2024-07-22 09:23:32","");
INSERT INTO sys_menu VALUES (1084,"测试套件",1068,1,"suite","qtr/suite/index",null,1,0,"C","0","0","qtr:suite:list","swagger","admin","2024-08-19 21:58:20","admin","2024-08-25 13:31:32","");
INSERT INTO sys_menu VALUES (1085,"执行计划",1068,2,"/qtr/job","qtr/job/index",null,1,0,"C","0","0","qtr:job:list","skill","admin","2024-08-19 21:58:20","admin","2024-08-25 14:55:23","");
INSERT INTO sys_menu VALUES (1086,"执行用例",1066,6,"",null,null,1,0,"F","0","0","hrm:case:test","#","admin","2024-08-30 14:09:56","admin","2024-08-30 14:09:56","");
INSERT INTO sys_menu VALUES (1088,"api详情",1081,1,"",null,null,1,0,"F","0","0","hrm:api:get","#","admin","2024-08-30 14:09:56","admin","2024-08-30 14:09:56","");
INSERT INTO sys_menu VALUES (1089,"新增api",1081,2,"",null,null,1,0,"F","0","0","hrm:api:add","#","admin","2024-08-30 14:09:56","admin","2024-08-30 14:09:56","");
INSERT INTO sys_menu VALUES (1090,"修改api",1081,3,"",null,null,1,0,"F","0","0","hrm:api:update","#","admin","2024-08-30 14:09:56","admin","2024-08-30 14:09:56","");
INSERT INTO sys_menu VALUES (1091,"删除api",1081,4,"",null,null,1,0,"F","0","0","hrm:api:delete","#","admin","2024-08-30 14:09:56","admin","2024-08-30 14:09:56","");
INSERT INTO sys_menu VALUES (1092,"执行api",1081,5,"",null,null,1,0,"F","0","0","hrm:api:debug","#","admin","2024-08-30 14:09:56","admin","2024-08-30 14:09:56","");
INSERT INTO sys_menu VALUES (1093,"api执行历史",1081,6,"",null,null,1,0,"F","0","0","hrm:api:history","#","admin","2024-08-30 14:09:56","admin","2024-08-30 14:09:56","");
INSERT INTO sys_menu VALUES (1094,"用例执行历史",1066,7,"",null,null,1,0,"F","0","0","hrm:case:history","#","admin","2024-08-30 14:09:56","admin","2024-08-30 14:09:56","");
INSERT INTO sys_menu VALUES (1095,"增加",1064,1,"",null,null,1,0,"F","0","0","hrm:debugtalk:add","#","admin","2024-09-02 10:39:04","admin","2024-09-02 10:39:04","");
INSERT INTO sys_menu VALUES (1096,"编辑",1064,2,"",null,null,1,0,"F","0","0","hrm:debugtalk:edit","#","admin","2024-09-02 10:39:04","admin","2024-09-02 10:39:04","");
INSERT INTO sys_menu VALUES (1097,"删除",1064,3,"",null,null,1,0,"F","0","0","hrm:debugtalk:remove","#","admin","2024-09-02 10:39:04","admin","2024-09-02 10:39:04","");
INSERT INTO sys_menu VALUES (1098,"详情",1064,4,"",null,null,1,0,"F","0","0","hrm:debugtalk:detail","#","admin","2024-09-02 10:39:04","admin","2024-09-02 10:39:04","");
INSERT INTO sys_menu VALUES (1099,"新增",1070,1,"",null,null,1,0,"F","0","0","hrm:env:add","#","admin","2024-09-02 10:39:04","admin","2024-09-02 10:39:04","");
INSERT INTO sys_menu VALUES (1100,"编辑",1070,2,"",null,null,1,0,"F","0","0","hrm:env:edit","#","admin","2024-09-02 10:39:04","admin","2024-09-02 10:39:04","");
INSERT INTO sys_menu VALUES (1101,"删除",1070,3,"",null,null,1,0,"F","0","0","hrm:env:remove","#","admin","2024-09-02 10:39:04","admin","2024-09-02 10:39:04","");
INSERT INTO sys_menu VALUES (1102,"复制",1070,4,"",null,null,1,0,"F","0","0","hrm:env:copy","#","admin","2024-09-02 10:39:04","admin","2024-09-02 11:14:47","");
INSERT INTO sys_menu VALUES (1103,"详情",1070,5,"",null,null,1,0,"F","0","0","hrm:env:detail","#","admin","2024-09-02 10:39:04","admin","2024-09-02 11:20:08","");
INSERT INTO sys_menu VALUES (1104,"详情",1069,1,"",null,null,1,0,"F","0","0","hrm:report:detail","#","admin","2024-09-02 11:19:37","admin","2024-09-02 11:19:37","");
INSERT INTO sys_menu VALUES (1105,"删除",1069,2,"",null,null,1,0,"F","0","0","hrm:report:delete","#","admin","2024-09-02 11:19:37","admin","2024-09-02 11:19:37","");
INSERT INTO sys_menu VALUES (1106,"复制",1066,8,"",null,null,1,0,"F","0","0","hrm:case:copy","#","admin","2024-09-02 11:19:37","admin","2024-09-02 11:19:37","");
INSERT INTO sys_menu VALUES (1107,"增加",1063,1,"",null,null,1,0,"F","0","0","hrm:project:add","#","admin","2024-09-02 11:19:37","admin","2024-09-02 11:19:37","");
INSERT INTO sys_menu VALUES (1108,"编辑",1063,2,"",null,null,1,0,"F","0","0","hrm:project:edit","#","admin","2024-09-02 11:19:37","admin","2024-09-02 11:19:37","");
INSERT INTO sys_menu VALUES (1109,"删除",1063,3,"",null,null,1,0,"F","0","0","hrm:project:remove","#","admin","2024-09-02 11:19:37","admin","2024-09-02 11:19:37","");
INSERT INTO sys_menu VALUES (1110,"查看执行历史详情",1066,9,"",null,null,1,0,"F","0","0","hrm:history:detail","#","admin","2024-09-03 19:06:37","admin","2024-09-03 19:06:37","");
INSERT INTO sys_menu VALUES (1111,"删除执行历史",1066,10,"",null,null,1,0,"F","0","0","hrm:history:delete","#","admin","2024-09-03 19:06:37","admin","2024-09-03 19:06:37","");
INSERT INTO sys_menu VALUES (1112,"查看执行历史详情",1081,7,"",null,null,1,0,"F","0","0","hrm:history:detail","#","admin","2024-09-03 19:06:37","admin","2024-09-03 19:06:37","");
INSERT INTO sys_menu VALUES (1113,"删除执行历史",1081,9,"",null,null,1,0,"F","0","0","hrm:history:delete","#","admin","2024-09-03 19:06:37","admin","2024-09-03 19:06:37","");
INSERT INTO sys_menu VALUES (1114,"用例执行",1063,4,"",null,null,1,0,"F","0","0","hrm:case:run","#","admin","2024-09-06 11:53:33","admin","2024-09-06 11:53:33","");
INSERT INTO sys_menu VALUES (1115,"新增",1084,1,"",null,null,1,0,"F","0","0","qtr:suite:add","#","admin","2024-09-10 17:42:52","admin","2024-09-10 17:42:52","");
INSERT INTO sys_menu VALUES (1116,"运行",1084,2,"",null,null,1,0,"F","0","0","hrm:case:run","#","admin","2024-09-10 17:42:52","admin","2024-09-10 17:42:52","");
INSERT INTO sys_menu VALUES (1117,"修改",1084,3,"",null,null,1,0,"F","0","0","qtr:suite:edit","#","admin","2024-09-10 17:42:52","admin","2024-09-10 17:42:52","");
INSERT INTO sys_menu VALUES (1118,"配置",1084,4,"",null,null,1,0,"F","0","0","qtr:suite:edit","#","admin","2024-09-10 17:42:52","admin","2024-09-10 17:42:52","");
INSERT INTO sys_menu VALUES (1119,"删除",1084,5,"",null,null,1,0,"F","0","0","qtr:suite:remove","#","admin","2024-09-10 17:42:52","admin","2024-09-10 17:42:52","");
INSERT INTO sys_menu VALUES (1123,"新增",1085,1,"",null,null,1,0,"F","0","0","qtr:job:add","#","admin","2024-09-25 17:28:28","admin","2024-09-25 17:28:28","");
INSERT INTO sys_menu VALUES (1128,"编辑",1085,2,"",null,null,1,0,"F","0","0","qtr:job:edit","#","admin","2024-09-25 17:28:28","admin","2024-09-25 17:28:28","");
INSERT INTO sys_menu VALUES (1133,"删除",1085,3,"",null,null,1,0,"F","0","0","qtr:job:remove","#","admin","2024-09-25 17:28:28","admin","2024-09-25 17:28:28","");
INSERT INTO sys_menu VALUES (1138,"导出",1085,4,"",null,null,1,0,"F","0","0","qtr:job:export","#","admin","2024-09-25 17:28:28","admin","2024-09-25 17:28:28","");
INSERT INTO sys_menu VALUES (1143,"日志",1085,5,"",null,null,1,0,"F","0","0","qtr:job:query","#","admin","2024-09-25 17:28:28","admin","2024-09-25 17:28:28","");
INSERT INTO sys_menu VALUES (1148,"执行",1085,6,"",null,null,1,0,"F","0","0","qtr:job:changeStatus","#","admin","2024-09-25 17:28:28","admin","2024-09-25 17:28:28","");
INSERT INTO sys_menu VALUES (1153,"环境管理",1061,7,"hrm",null,null,1,0,"M","0","0",null,"size","admin","2024-10-23 14:55:13","admin","2024-10-24 19:30:33","");
INSERT INTO sys_menu VALUES (1158,"Agent管理",1153,2,"agent","hrm/agent/index",null,1,0,"C","0","0","qtr:agent:list","druid","admin","2024-10-23 14:55:13","admin","2024-11-04 19:27:46","");
INSERT INTO sys_menu VALUES (1163,"转发管理",1153,3,"forwarding","hrm/forward/index",null,1,0,"C","0","0","qtr:forwardRules:list","code","admin","2024-10-23 14:55:13","admin","2024-11-04 20:02:28","");
INSERT INTO sys_menu VALUES (1168,"编辑",1158,1,"",null,null,1,0,"F","0","0","qtr:agent:edit","#","admin","2024-11-04 19:24:03","admin","2024-11-04 19:24:03","");
INSERT INTO sys_menu VALUES (1173,"删除",1158,2,"",null,null,1,0,"F","0","0","qtr:agent:remove","#","admin","2024-11-04 19:24:03","admin","2024-11-04 19:24:03","");
INSERT INTO sys_menu VALUES (1178,"新增",1163,1,"",null,null,1,0,"F","0","0","qtr:forwardRules:add","#","admin","2024-11-04 19:24:03","admin","2024-11-04 20:03:09","");
INSERT INTO sys_menu VALUES (1183,"编辑",1163,2,"",null,null,1,0,"F","0","0","qtr:forwardRules:edit","#","admin","2024-11-04 19:24:03","admin","2024-11-04 20:03:15","");
INSERT INTO sys_menu VALUES (1188,"删除",1163,3,"",null,null,1,0,"F","0","0","qtr:forwardRules:remove","#","admin","2024-11-04 19:24:03","admin","2024-11-04 20:03:21","");
INSERT INTO sys_menu VALUES (1193,"复制",1163,4,"",null,null,1,0,"F","0","0","qtr:forwardRules:copy","#","admin","2024-11-04 19:24:03","admin","2024-11-04 20:03:26","");
INSERT INTO sys_menu VALUES (1198,"详情",1163,5,"",null,null,1,0,"F","0","0","qtr:forwardRules:detail","#","admin","2024-11-04 20:37:09","admin","2024-11-04 20:37:09","");
"""
    new_lines = []
    for line in data.split('\n'):
        if line.strip() != '':
            line_split = line.split(",")
            line_split[-2] = "null"
            line_split[-4] = "sysdate()"
            line = ",".join(line_split)
            new_lines.append(line)
    print("\n".join(new_lines))