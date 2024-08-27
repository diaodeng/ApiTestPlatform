from sqlalchemy.orm import Session
from module_hrm.dao.api_dao import ApiOperation
from module_hrm.entity.do.api_do import ApiInfo
from module_hrm.entity.vo.api_vo import ApiQueryModel
from module_hrm.enums.enums import DataType


def api_dir_tree(request):
    """
    返回API的目录树，供新建目录或者API的时候选择父目录
    """
    name = request.GET.get("name")

    def node(api_obj, all_children_data: list = []):
        children_data = []
        for index, child in enumerate(all_children_data):
            if child.get("parent_id", None) == api_obj.id:
                children_data.append(child)
                all_children_data.pop(index)
        node_data = {
            "id": api_obj.id,
            "name": f'{api_obj.name}',
            "title": api_obj.interface or api_obj.name,
            "isParent": "true" if api_obj.type == DataType.folder.value else "false",
            "parent_id": api_obj.parent_id,
            "data": ""
        }
        if api_obj.type == DataType.folder.value:
            node_data["children"] = children_data or []
        return node_data

    def data_handle(dirs_obj, nodes: list = []):
        all_dir = dirs_obj
        for child in all_dir:
            child_node = node(child)
            nodes.append(child_node)
            all_dir_ids = [d.id for d in all_dir]
            ApiInfo.objects.filter(id__in=all_dir_ids).all()

    all_tree_data = []
    all_result = ApiInfo.objects.filter(type=DataType.folder.value)
    if name:
        all_result = all_result.filter(name__contains=name)

    data_handle(all_result.all(), all_tree_data)

    return all_tree_data


def api_tree(query_db: Session, query_info):
    """
    这个实现从根目录开始
    """

    def node_handle(api_obj):
        node_data = {
            'edit': False,
            "api_id": api_obj.api_id,
            "name": f'{api_obj.name}',
            "title": api_obj.interface or api_obj.name,
            "isParent": True if api_obj.type == DataType.folder.value else False,
            "parent_id": api_obj.parent_id,
            "data": {
                "isParent": True if api_obj.type == DataType.folder.value else False,
                "parent_id": api_obj.parent_id
            }
        }
        return node_data

    def node_handle2(api_obj):
        node_data = {
            "id": api_obj.id,
            "name": f'{api_obj.name}',
            "title": api_obj.interface or api_obj.name,
            "isParent": True if api_obj.type == DataType.folder.value else False,
            "parent_id": api_obj.parent_id,
            "data": {
                "isParent": True if api_obj.type == DataType.folder.value else False,
                "parent_id": api_obj.parent_id
            }
        }
        return node_data

    def data_handle(parent_node_data, children_obj, not_root_nodes_data):
        for node in children_obj:
            node_data = node
            parent_node_data.setdefault("children", []).append(node_data)
            childrens = []
            new_not_root_nodes_data = []
            for nrd in not_root_nodes_data:
                if nrd["parent_id"] == node["api_id"]:
                    childrens.append(nrd)
                else:
                    new_not_root_nodes_data.append(nrd)

            if len(childrens) > 0:
                data_handle(node_data, childrens, new_not_root_nodes_data)

    root_node = {"children": []}
    root_nodes = query_db.query(ApiInfo).filter(ApiInfo.parent_id == None).all()
    root_nodes = [node_handle(root_node) for root_node in root_nodes]

    not_root_nodes_obj = query_db.query(ApiInfo).filter(ApiInfo.parent_id != None).all()
    not_root_nodes_data = [node_handle(node) for node in not_root_nodes_obj]

    data_handle(root_node, root_nodes, not_root_nodes_data)
    return root_node["children"]


def api_tree_from_children(query_db: Session, user_id=None):
    """
    这个实现从api反向向上
    """

    def node(api_obj, all_children_data: list = []):
        children_data = []
        for index, child in enumerate(all_children_data):
            if child.get("parent_id", None) == api_obj.id:
                children_data.append(child)
                # all_children_data.pop(index)
        node_data = {
            "id": api_obj.id,
            "name": f'{api_obj.name}',
            "title": api_obj.interface or api_obj.name,
            "isParent": True if api_obj.type == DataType.folder.value else False,
            "parent_id": api_obj.parent_id,
            "data": {
                "isParent": True if api_obj.type == DataType.folder.value else False,
                "parent_id": api_obj.parent_id
            }
        }
        if api_obj.type == DataType.folder.value:
            node_data["children"] = children_data or []
        return node_data

    def data_handle(apis_obj, all_data: list, all_children_data: list = []):
        all_interface = apis_obj.filter(parent_id__isnull=True).all()
        # all_data.extend([node(api, all_children_data) for api in all_interface])
        for api in all_interface:
            if api.id in all_data:
                all_data[api.id].get("children", []).extend(node(api, all_children_data).get("children", []))
            else:
                all_data[api.id] = node(api, all_children_data)

        interface_has_parent = apis_obj.filter(parent_id__isnull=False).all()
        if interface_has_parent:  # 有数据就继续
            interface_has_parent_data = [node(api, all_children_data) for api in interface_has_parent]
            parent_ids = [api.parent_id for api in interface_has_parent]
            parent_ids = list(set(parent_ids))
            parent_node = query_db.query(ApiInfo).filter(ApiInfo.api_id.in_(parent_ids))
            data_handle(parent_node, all_data, interface_has_parent_data)

    all_tree_data = {}
    all_result = query_db.query(ApiInfo).filter(ApiInfo.type == DataType.api.value)

    data_handle(all_result, all_tree_data, [])

    all_data = all_tree_data.values()
    return all_data
