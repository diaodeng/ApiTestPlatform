-- ----------------------------
-- 1、部门表
-- ----------------------------
drop table if exists sys_dept;
create table sys_dept (
  dept_id           bigint(20)      not null auto_increment    comment '部门id',
  parent_id         bigint(20)      default 0                  comment '父部门id',
  ancestors         varchar(50)     default ''                 comment '祖级列表',
  dept_name         varchar(30)     default ''                 comment '部门名称',
  order_num         int(4)          default 0                  comment '显示顺序',
  leader            varchar(20)     default null               comment '负责人',
  phone             varchar(11)     default null               comment '联系电话',
  email             varchar(50)     default null               comment '邮箱',
  status            char(1)         default '0'                comment '部门状态（0正常 1停用）',
  del_flag          char(1)         default '0'                comment '删除标志（0代表存在 2代表删除）',
  create_by         varchar(64)     default ''                 comment '创建者',
  create_time 	    datetime                                   comment '创建时间',
  update_by         varchar(64)     default ''                 comment '更新者',
  update_time       datetime                                   comment '更新时间',
  primary key (dept_id)
) engine=innodb auto_increment=200 comment = '部门表';

-- ----------------------------
-- 初始化-部门表数据
-- ----------------------------
insert into sys_dept values(100,  0,   '0',          '集团总公司',   0, '年糕', '15888888888', 'niangao@qq.com', '0', '0', 'admin', sysdate(), '', null);
insert into sys_dept values(101,  100, '0,100',      '深圳分公司', 1, '年糕', '15888888888', 'niangao@qq.com', '0', '0', 'admin', sysdate(), '', null);
insert into sys_dept values(102,  100, '0,100',      '长沙分公司', 2, '年糕', '15888888888', 'niangao@qq.com', '0', '0', 'admin', sysdate(), '', null);
insert into sys_dept values(103,  101, '0,100,101',  '研发部门',   1, '年糕', '15888888888', 'niangao@qq.com', '0', '0', 'admin', sysdate(), '', null);
insert into sys_dept values(104,  101, '0,100,101',  '市场部门',   2, '年糕', '15888888888', 'niangao@qq.com', '0', '0', 'admin', sysdate(), '', null);
insert into sys_dept values(105,  101, '0,100,101',  '测试部门',   3, '年糕', '15888888888', 'niangao@qq.com', '0', '0', 'admin', sysdate(), '', null);
insert into sys_dept values(106,  101, '0,100,101',  '财务部门',   4, '年糕', '15888888888', 'niangao@qq.com', '0', '0', 'admin', sysdate(), '', null);
insert into sys_dept values(107,  101, '0,100,101',  '运维部门',   5, '年糕', '15888888888', 'niangao@qq.com', '0', '0', 'admin', sysdate(), '', null);
insert into sys_dept values(108,  102, '0,100,102',  '市场部门',   1, '年糕', '15888888888', 'niangao@qq.com', '0', '0', 'admin', sysdate(), '', null);
insert into sys_dept values(109,  102, '0,100,102',  '财务部门',   2, '年糕', '15888888888', 'niangao@qq.com', '0', '0', 'admin', sysdate(), '', null);


-- ----------------------------
-- 2、用户信息表
-- ----------------------------
drop table if exists sys_user;
create table sys_user (
  user_id           bigint(20)      not null auto_increment    comment '用户ID',
  dept_id           bigint(20)      default null               comment '部门ID',
  user_name         varchar(30)     not null                   comment '用户账号',
  nick_name         varchar(30)     not null                   comment '用户昵称',
  user_type         varchar(2)      default '00'               comment '用户类型（00系统用户）',
  email             varchar(50)     default ''                 comment '用户邮箱',
  phonenumber       varchar(11)     default ''                 comment '手机号码',
  sex               char(1)         default '0'                comment '用户性别（0男 1女 2未知）',
  avatar            varchar(100)    default ''                 comment '头像地址',
  password          varchar(100)    default ''                 comment '密码',
  status            char(1)         default '0'                comment '帐号状态（0正常 1停用）',
  del_flag          char(1)         default '0'                comment '删除标志（0代表存在 2代表删除）',
  login_ip          varchar(128)    default ''                 comment '最后登录IP',
  login_date        datetime                                   comment '最后登录时间',
  create_by         varchar(64)     default ''                 comment '创建者',
  create_time       datetime                                   comment '创建时间',
  update_by         varchar(64)     default ''                 comment '更新者',
  update_time       datetime                                   comment '更新时间',
  remark            varchar(500)    default null               comment '备注',
  primary key (user_id)
) engine=innodb auto_increment=100 comment = '用户信息表';

-- ----------------------------
-- 初始化-用户信息表数据
-- ----------------------------
insert into sys_user values(1,  103, 'admin',   '超级管理员', '00', 'niangao@163.com', '15888888888', '1', '', '$2a$10$7JB720yubVSZvUI0rEqK/.VqGOZTH.ulu33dHOiBE8ByOhJIrdAu2', '0', '0', '127.0.0.1', sysdate(), 'admin', sysdate(), '', null, '管理员');
insert into sys_user values(2,  105, 'niangao', '年糕', 			'00', 'niangao@qq.com',  '15666666666', '1', '', '$2a$10$7JB720yubVSZvUI0rEqK/.VqGOZTH.ulu33dHOiBE8ByOhJIrdAu2', '0', '0', '127.0.0.1', sysdate(), 'admin', sysdate(), '', null, '测试员');


-- ----------------------------
-- 3、岗位信息表
-- ----------------------------
drop table if exists sys_post;
create table sys_post
(
  post_id       bigint(20)      not null auto_increment    comment '岗位ID',
  post_code     varchar(64)     not null                   comment '岗位编码',
  post_name     varchar(50)     not null                   comment '岗位名称',
  post_sort     int(4)          not null                   comment '显示顺序',
  status        char(1)         not null                   comment '状态（0正常 1停用）',
  create_by     varchar(64)     default ''                 comment '创建者',
  create_time   datetime                                   comment '创建时间',
  update_by     varchar(64)     default ''			       comment '更新者',
  update_time   datetime                                   comment '更新时间',
  remark        varchar(500)    default null               comment '备注',
  primary key (post_id)
) engine=innodb comment = '岗位信息表';

-- ----------------------------
-- 初始化-岗位信息表数据
-- ----------------------------
insert into sys_post values(1, 'ceo',  '董事长',    1, '0', 'admin', sysdate(), '', null, '');
insert into sys_post values(2, 'se',   '项目经理',  2, '0', 'admin', sysdate(), '', null, '');
insert into sys_post values(3, 'hr',   '人力资源',  3, '0', 'admin', sysdate(), '', null, '');
insert into sys_post values(4, 'user', '普通员工',  4, '0', 'admin', sysdate(), '', null, '');


-- ----------------------------
-- 4、角色信息表
-- ----------------------------
drop table if exists sys_role;
create table sys_role (
  role_id              bigint(20)      not null auto_increment    comment '角色ID',
  role_name            varchar(30)     not null                   comment '角色名称',
  role_key             varchar(100)    not null                   comment '角色权限字符串',
  role_sort            int(4)          not null                   comment '显示顺序',
  data_scope           char(1)         default '1'                comment '数据范围（1：全部数据权限 2：自定数据权限 3：本部门数据权限 4：本部门及以下数据权限）',
  menu_check_strictly  tinyint(1)      default 1                  comment '菜单树选择项是否关联显示',
  dept_check_strictly  tinyint(1)      default 1                  comment '部门树选择项是否关联显示',
  status               char(1)         not null                   comment '角色状态（0正常 1停用）',
  del_flag             char(1)         default '0'                comment '删除标志（0代表存在 2代表删除）',
  create_by            varchar(64)     default ''                 comment '创建者',
  create_time          datetime                                   comment '创建时间',
  update_by            varchar(64)     default ''                 comment '更新者',
  update_time          datetime                                   comment '更新时间',
  remark               varchar(500)    default null               comment '备注',
  primary key (role_id)
) engine=innodb auto_increment=100 comment = '角色信息表';

-- ----------------------------
-- 初始化-角色信息表数据
-- ----------------------------
insert into sys_role values('1', '超级管理员',  'admin',  1, 1, 1, 1, '0', '0', 'admin', sysdate(), '', null, '超级管理员');
insert into sys_role values('2', '普通角色',    'common', 2, 2, 1, 1, '0', '0', 'admin', sysdate(), '', null, '普通角色');


-- ----------------------------
-- 5、菜单权限表
-- ----------------------------
drop table if exists sys_menu;
create table sys_menu (
  menu_id           bigint(20)      not null auto_increment    comment '菜单ID',
  menu_name         varchar(50)     not null                   comment '菜单名称',
  parent_id         bigint(20)      default 0                  comment '父菜单ID',
  order_num         int(4)          default 0                  comment '显示顺序',
  path              varchar(200)    default ''                 comment '路由地址',
  component         varchar(255)    default null               comment '组件路径',
  query             varchar(255)    default null               comment '路由参数',
  is_frame          int(1)          default 1                  comment '是否为外链（0是 1否）',
  is_cache          int(1)          default 0                  comment '是否缓存（0缓存 1不缓存）',
  menu_type         char(1)         default ''                 comment '菜单类型（M目录 C菜单 F按钮）',
  visible           char(1)         default 0                  comment '菜单状态（0显示 1隐藏）',
  status            char(1)         default 0                  comment '菜单状态（0正常 1停用）',
  perms             varchar(100)    default null               comment '权限标识',
  icon              varchar(100)    default '#'                comment '菜单图标',
  create_by         varchar(64)     default ''                 comment '创建者',
  create_time       datetime                                   comment '创建时间',
  update_by         varchar(64)     default ''                 comment '更新者',
  update_time       datetime                                   comment '更新时间',
  remark            varchar(500)    default ''                 comment '备注',
  primary key (menu_id)
) engine=innodb auto_increment=2000 comment = '菜单权限表';

-- ----------------------------
-- 初始化-菜单信息表数据
-- ----------------------------
-- 一级菜单
insert into sys_menu values('1', '系统管理', '0', '1', 'system',           null, '', 1, 0, 'M', '0', '0', '', 'system',   'admin', sysdate(), '', null, '系统管理目录');
insert into sys_menu values('2', '系统监控', '0', '2', 'monitor',          null, '', 1, 0, 'M', '0', '0', '', 'monitor',  'admin', sysdate(), '', null, '系统监控目录');
insert into sys_menu values('3', '系统工具', '0', '3', 'tool',             null, '', 1, 0, 'M', '0', '0', '', 'tool',     'admin', sysdate(), '', null, '系统工具目录');
insert into sys_menu values('4', '若依官网', '0', '4', 'http://ruoyi.vip', null, '', 0, 0, 'M', '0', '0', '', 'guide',    'admin', sysdate(), '', null, '若依官网地址');
-- 二级菜单
insert into sys_menu values('100',  '用户管理', '1',   '1', 'user',       'system/user/index',        '', 1, 0, 'C', '0', '0', 'system:user:list',        'user',          'admin', sysdate(), '', null, '用户管理菜单');
insert into sys_menu values('101',  '角色管理', '1',   '2', 'role',       'system/role/index',        '', 1, 0, 'C', '0', '0', 'system:role:list',        'peoples',       'admin', sysdate(), '', null, '角色管理菜单');
insert into sys_menu values('102',  '菜单管理', '1',   '3', 'menu',       'system/menu/index',        '', 1, 0, 'C', '0', '0', 'system:menu:list',        'tree-table',    'admin', sysdate(), '', null, '菜单管理菜单');
insert into sys_menu values('103',  '部门管理', '1',   '4', 'dept',       'system/dept/index',        '', 1, 0, 'C', '0', '0', 'system:dept:list',        'tree',          'admin', sysdate(), '', null, '部门管理菜单');
insert into sys_menu values('104',  '岗位管理', '1',   '5', 'post',       'system/post/index',        '', 1, 0, 'C', '0', '0', 'system:post:list',        'post',          'admin', sysdate(), '', null, '岗位管理菜单');
insert into sys_menu values('105',  '字典管理', '1',   '6', 'dict',       'system/dict/index',        '', 1, 0, 'C', '0', '0', 'system:dict:list',        'dict',          'admin', sysdate(), '', null, '字典管理菜单');
insert into sys_menu values('106',  '参数设置', '1',   '7', 'paramConfig',     'system/config/index',      '', 1, 0, 'C', '0', '0', 'system:config:list',      'edit',          'admin', sysdate(), '', null, '参数设置菜单');
insert into sys_menu values('107',  '通知公告', '1',   '8', 'notice',     'system/notice/index',      '', 1, 0, 'C', '0', '0', 'system:notice:list',      'message',       'admin', sysdate(), '', null, '通知公告菜单');
insert into sys_menu values('108',  '日志管理', '1',   '9', 'log',        '',                         '', 1, 0, 'M', '0', '0', '',                        'log',           'admin', sysdate(), '', null, '日志管理菜单');
insert into sys_menu values('109',  '在线用户', '2',   '1', 'online',     'monitor/online/index',     '', 1, 0, 'C', '0', '0', 'monitor:online:list',     'online',        'admin', sysdate(), '', null, '在线用户菜单');
insert into sys_menu values('110',  '定时任务', '2',   '2', 'job',        'monitor/job/index',        '', 1, 0, 'C', '0', '0', 'monitor:job:list',        'job',           'admin', sysdate(), '', null, '定时任务菜单');
insert into sys_menu values('111',  '数据监控', '2',   '3', 'druid',      'monitor/druid/index',      '', 1, 0, 'C', '0', '0', 'monitor:druid:list',      'druid',         'admin', sysdate(), '', null, '数据监控菜单');
insert into sys_menu values('112',  '服务监控', '2',   '4', 'server',     'monitor/server/index',     '', 1, 0, 'C', '0', '0', 'monitor:server:list',     'server',        'admin', sysdate(), '', null, '服务监控菜单');
insert into sys_menu values('113',  '缓存监控', '2',   '5', 'cache',      'monitor/cache/index',      '', 1, 0, 'C', '0', '0', 'monitor:cache:list',      'redis',         'admin', sysdate(), '', null, '缓存监控菜单');
insert into sys_menu values('114',  '缓存列表', '2',   '6', 'cacheList',  'monitor/cache/list',       '', 1, 0, 'C', '0', '0', 'monitor:cache:list',      'redis-list',    'admin', sysdate(), '', null, '缓存列表菜单');
insert into sys_menu values('115',  '表单构建', '3',   '1', 'build',      'tool/build/index',         '', 1, 0, 'C', '0', '0', 'tool:build:list',         'build',         'admin', sysdate(), '', null, '表单构建菜单');
insert into sys_menu values('116',  '代码生成', '3',   '2', 'gen',        'tool/gen/index',           '', 1, 0, 'C', '0', '0', 'tool:gen:list',           'code',          'admin', sysdate(), '', null, '代码生成菜单');
insert into sys_menu values('117',  '系统接口', '3',   '3', 'swagger',    'tool/swagger/index',       '', 1, 0, 'C', '0', '0', 'tool:swagger:list',       'swagger',       'admin', sysdate(), '', null, '系统接口菜单');

-- 三级菜单
insert into sys_menu values('500',  '操作日志', '108', '1', 'operlog',    'monitor/operlog/index',    '', 1, 0, 'C', '0', '0', 'monitor:operlog:list',    'form',          'admin', sysdate(), '', null, '操作日志菜单');
insert into sys_menu values('501',  '登录日志', '108', '2', 'logininfor', 'monitor/logininfor/index', '', 1, 0, 'C', '0', '0', 'monitor:logininfor:list', 'logininfor',    'admin', sysdate(), '', null, '登录日志菜单');
insert into sys_menu values('502',  'Logger列表', '108',   '3', 'loggerList',  'monitor/logger/list',       '', 1, 0, 'C', '0', '0', 'monitor:logger:list',      'log',    'admin', sysdate(), '', null, 'Logger列表菜单');

-- 用户管理按钮
insert into sys_menu values('1000', '用户查询', '100', '1',  '', '', '', 1, 0, 'F', '0', '0', 'system:user:query',          '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1001', '用户新增', '100', '2',  '', '', '', 1, 0, 'F', '0', '0', 'system:user:add',            '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1002', '用户修改', '100', '3',  '', '', '', 1, 0, 'F', '0', '0', 'system:user:edit',           '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1003', '用户删除', '100', '4',  '', '', '', 1, 0, 'F', '0', '0', 'system:user:remove',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1004', '用户导出', '100', '5',  '', '', '', 1, 0, 'F', '0', '0', 'system:user:export',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1005', '用户导入', '100', '6',  '', '', '', 1, 0, 'F', '0', '0', 'system:user:import',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1006', '重置密码', '100', '7',  '', '', '', 1, 0, 'F', '0', '0', 'system:user:resetPwd',       '#', 'admin', sysdate(), '', null, '');
-- 角色管理按钮
insert into sys_menu values('1007', '角色查询', '101', '1',  '', '', '', 1, 0, 'F', '0', '0', 'system:role:query',          '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1008', '角色新增', '101', '2',  '', '', '', 1, 0, 'F', '0', '0', 'system:role:add',            '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1009', '角色修改', '101', '3',  '', '', '', 1, 0, 'F', '0', '0', 'system:role:edit',           '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1010', '角色删除', '101', '4',  '', '', '', 1, 0, 'F', '0', '0', 'system:role:remove',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1011', '角色导出', '101', '5',  '', '', '', 1, 0, 'F', '0', '0', 'system:role:export',         '#', 'admin', sysdate(), '', null, '');
-- 菜单管理按钮
insert into sys_menu values('1012', '菜单查询', '102', '1',  '', '', '', 1, 0, 'F', '0', '0', 'system:menu:query',          '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1013', '菜单新增', '102', '2',  '', '', '', 1, 0, 'F', '0', '0', 'system:menu:add',            '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1014', '菜单修改', '102', '3',  '', '', '', 1, 0, 'F', '0', '0', 'system:menu:edit',           '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1015', '菜单删除', '102', '4',  '', '', '', 1, 0, 'F', '0', '0', 'system:menu:remove',         '#', 'admin', sysdate(), '', null, '');
-- 部门管理按钮
insert into sys_menu values('1016', '部门查询', '103', '1',  '', '', '', 1, 0, 'F', '0', '0', 'system:dept:query',          '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1017', '部门新增', '103', '2',  '', '', '', 1, 0, 'F', '0', '0', 'system:dept:add',            '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1018', '部门修改', '103', '3',  '', '', '', 1, 0, 'F', '0', '0', 'system:dept:edit',           '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1019', '部门删除', '103', '4',  '', '', '', 1, 0, 'F', '0', '0', 'system:dept:remove',         '#', 'admin', sysdate(), '', null, '');
-- 岗位管理按钮
insert into sys_menu values('1020', '岗位查询', '104', '1',  '', '', '', 1, 0, 'F', '0', '0', 'system:post:query',          '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1021', '岗位新增', '104', '2',  '', '', '', 1, 0, 'F', '0', '0', 'system:post:add',            '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1022', '岗位修改', '104', '3',  '', '', '', 1, 0, 'F', '0', '0', 'system:post:edit',           '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1023', '岗位删除', '104', '4',  '', '', '', 1, 0, 'F', '0', '0', 'system:post:remove',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1024', '岗位导出', '104', '5',  '', '', '', 1, 0, 'F', '0', '0', 'system:post:export',         '#', 'admin', sysdate(), '', null, '');
-- 字典管理按钮
insert into sys_menu values('1025', '字典查询', '105', '1', '#', '', '', 1, 0, 'F', '0', '0', 'system:dict:query',          '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1026', '字典新增', '105', '2', '#', '', '', 1, 0, 'F', '0', '0', 'system:dict:add',            '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1027', '字典修改', '105', '3', '#', '', '', 1, 0, 'F', '0', '0', 'system:dict:edit',           '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1028', '字典删除', '105', '4', '#', '', '', 1, 0, 'F', '0', '0', 'system:dict:remove',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1029', '字典导出', '105', '5', '#', '', '', 1, 0, 'F', '0', '0', 'system:dict:export',         '#', 'admin', sysdate(), '', null, '');
-- 参数设置按钮
insert into sys_menu values('1030', '参数查询', '106', '1', '#', '', '', 1, 0, 'F', '0', '0', 'system:config:query',        '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1031', '参数新增', '106', '2', '#', '', '', 1, 0, 'F', '0', '0', 'system:config:add',          '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1032', '参数修改', '106', '3', '#', '', '', 1, 0, 'F', '0', '0', 'system:config:edit',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1033', '参数删除', '106', '4', '#', '', '', 1, 0, 'F', '0', '0', 'system:config:remove',       '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1034', '参数导出', '106', '5', '#', '', '', 1, 0, 'F', '0', '0', 'system:config:export',       '#', 'admin', sysdate(), '', null, '');
-- 通知公告按钮
insert into sys_menu values('1035', '公告查询', '107', '1', '#', '', '', 1, 0, 'F', '0', '0', 'system:notice:query',        '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1036', '公告新增', '107', '2', '#', '', '', 1, 0, 'F', '0', '0', 'system:notice:add',          '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1037', '公告修改', '107', '3', '#', '', '', 1, 0, 'F', '0', '0', 'system:notice:edit',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1038', '公告删除', '107', '4', '#', '', '', 1, 0, 'F', '0', '0', 'system:notice:remove',       '#', 'admin', sysdate(), '', null, '');
-- 操作日志按钮
insert into sys_menu values('1039', '操作查询', '500', '1', '#', '', '', 1, 0, 'F', '0', '0', 'monitor:operlog:query',      '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1040', '操作删除', '500', '2', '#', '', '', 1, 0, 'F', '0', '0', 'monitor:operlog:remove',     '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1041', '日志导出', '500', '3', '#', '', '', 1, 0, 'F', '0', '0', 'monitor:operlog:export',     '#', 'admin', sysdate(), '', null, '');
-- 登录日志按钮
insert into sys_menu values('1042', '登录查询', '501', '1', '#', '', '', 1, 0, 'F', '0', '0', 'monitor:logininfor:query',   '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1043', '登录删除', '501', '2', '#', '', '', 1, 0, 'F', '0', '0', 'monitor:logininfor:remove',  '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1044', '日志导出', '501', '3', '#', '', '', 1, 0, 'F', '0', '0', 'monitor:logininfor:export',  '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1045', '账户解锁', '501', '4', '#', '', '', 1, 0, 'F', '0', '0', 'monitor:logininfor:unlock',  '#', 'admin', sysdate(), '', null, '');
-- 在线用户按钮
insert into sys_menu values('1046', '在线查询', '109', '1', '#', '', '', 1, 0, 'F', '0', '0', 'monitor:online:query',       '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1047', '批量强退', '109', '2', '#', '', '', 1, 0, 'F', '0', '0', 'monitor:online:batchLogout', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1048', '单条强退', '109', '3', '#', '', '', 1, 0, 'F', '0', '0', 'monitor:online:forceLogout', '#', 'admin', sysdate(), '', null, '');
-- 定时任务按钮
insert into sys_menu values('1049', '任务查询', '110', '1', '#', '', '', 1, 0, 'F', '0', '0', 'monitor:job:query',          '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1050', '任务新增', '110', '2', '#', '', '', 1, 0, 'F', '0', '0', 'monitor:job:add',            '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1051', '任务修改', '110', '3', '#', '', '', 1, 0, 'F', '0', '0', 'monitor:job:edit',           '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1052', '任务删除', '110', '4', '#', '', '', 1, 0, 'F', '0', '0', 'monitor:job:remove',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1053', '状态修改', '110', '5', '#', '', '', 1, 0, 'F', '0', '0', 'monitor:job:changeStatus',   '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1054', '任务导出', '110', '6', '#', '', '', 1, 0, 'F', '0', '0', 'monitor:job:export',         '#', 'admin', sysdate(), '', null, '');
-- 代码生成按钮
insert into sys_menu values('1055', '生成查询', '116', '1', '#', '', '', 1, 0, 'F', '0', '0', 'tool:gen:query',             '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1056', '生成修改', '116', '2', '#', '', '', 1, 0, 'F', '0', '0', 'tool:gen:edit',              '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1057', '生成删除', '116', '3', '#', '', '', 1, 0, 'F', '0', '0', 'tool:gen:remove',            '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1058', '导入代码', '116', '4', '#', '', '', 1, 0, 'F', '0', '0', 'tool:gen:import',            '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1059', '预览代码', '116', '5', '#', '', '', 1, 0, 'F', '0', '0', 'tool:gen:preview',           '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1060', '生成代码', '116', '6', '#', '', '', 1, 0, 'F', '0', '0', 'tool:gen:code',              '#', 'admin', sysdate(), '', null, '');

-- 测试相关
INSERT INTO sys_menu VALUES (1061,"测试管理",0,1,"hrm",null,null,1,0,"M","0","0",null,"component","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1062,"项目管理",1061,1,"project","hrm/project/index",null,1,0,"M","0","0","hrm:project:list","clipboard","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1063,"项目列表",1062,1,"project","hrm/project/index",null,1,0,"C","0","0","hrm:project:list","clipboard","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1064,"DebugTalk.py",1062,2,"debugtalk","hrm/debugtalk/index",null,1,0,"C","0","0","hrm:debugtalk:list","code","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1065,"模块管理",1061,2,"module","hrm/module/index",null,1,0,"C","0","0","hrm:module:list","example","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1066,"用例管理",1061,4,"case","hrm/case/index",null,1,0,"C","0","0","hrm:case:list","size","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1067,"配置管理",1061,3,"config","hrm/config/index",null,1,0,"C","0","0","hrm:config:list","system","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1068,"测试计划",1061,5,"qtr","",null,1,0,"M","0","0","","skill","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1069,"报告管理",1061,6,"report","hrm/report/index",null,1,0,"C","0","0","hrm:report:list","redis-list","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1070,"环境管理",1153,1,"env","hrm/env/index",null,1,0,"C","0","0","hrm:env:list","textarea","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1071,"新增",1066,0,"",null,null,1,0,"F","0","0","hrm:case:add","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1072,"修改-确定",1066,1,"",null,null,1,0,"F","0","0","hrm:case:edit","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1073,"删除",1066,2,"",null,null,1,0,"F","0","0","hrm:case:remove","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1074,"导出",1066,3,"",null,null,1,0,"F","0","0","hrm:case:export","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1075,"修改-查看详情",1066,4,"",null,null,1,0,"F","0","0","hrm:case:detail","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1076,"修改",1065,0,"",null,null,1,0,"F","0","0","hrm:module:edit","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1077,"删除",1065,1,"",null,null,1,0,"F","0","0","hrm:module:remove","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1078,"导出",1065,2,"",null,null,1,0,"F","0","0","hrm:module:export","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1079,"新增",1065,3,"",null,null,1,0,"F","0","0","hrm:module:add","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1080,"查看详情",1065,4,"",null,null,1,0,"F","0","0","hrm:module:detail","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1081,"接口管理",1061,8,"api","hrm/api/index",null,1,0,"C","0","0","hrm:api:tree","icon","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1083,"用例调试",1066,5,"",null,null,1,0,"F","0","0","hrm:case:debug","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1084,"测试套件",1068,1,"suite","qtr/suite/index",null,1,0,"C","0","0","qtr:suite:list","swagger","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1085,"执行计划",1068,2,"/qtr/job","qtr/job/index",null,1,0,"C","0","0","qtr:job:list","skill","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1086,"执行用例",1066,6,"",null,null,1,0,"F","0","0","hrm:case:test","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1088,"api详情",1081,1,"",null,null,1,0,"F","0","0","hrm:api:get","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1089,"新增api",1081,2,"",null,null,1,0,"F","0","0","hrm:api:add","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1090,"修改api",1081,3,"",null,null,1,0,"F","0","0","hrm:api:update","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1091,"删除api",1081,4,"",null,null,1,0,"F","0","0","hrm:api:delete","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1092,"执行api",1081,5,"",null,null,1,0,"F","0","0","hrm:api:debug","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1093,"api执行历史",1081,6,"",null,null,1,0,"F","0","0","hrm:api:history","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1094,"用例执行历史",1066,7,"",null,null,1,0,"F","0","0","hrm:case:history","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1095,"增加",1064,1,"",null,null,1,0,"F","0","0","hrm:debugtalk:add","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1096,"编辑",1064,2,"",null,null,1,0,"F","0","0","hrm:debugtalk:edit","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1097,"删除",1064,3,"",null,null,1,0,"F","0","0","hrm:debugtalk:remove","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1098,"详情",1064,4,"",null,null,1,0,"F","0","0","hrm:debugtalk:detail","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1099,"新增",1070,1,"",null,null,1,0,"F","0","0","hrm:env:add","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1100,"编辑",1070,2,"",null,null,1,0,"F","0","0","hrm:env:edit","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1101,"删除",1070,3,"",null,null,1,0,"F","0","0","hrm:env:remove","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1102,"复制",1070,4,"",null,null,1,0,"F","0","0","hrm:env:copy","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1103,"详情",1070,5,"",null,null,1,0,"F","0","0","hrm:env:detail","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1104,"详情",1069,1,"",null,null,1,0,"F","0","0","hrm:report:detail","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1105,"删除",1069,2,"",null,null,1,0,"F","0","0","hrm:report:delete","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1106,"复制",1066,8,"",null,null,1,0,"F","0","0","hrm:case:copy","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1107,"增加",1063,1,"",null,null,1,0,"F","0","0","hrm:project:add","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1108,"编辑",1063,2,"",null,null,1,0,"F","0","0","hrm:project:edit","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1109,"删除",1063,3,"",null,null,1,0,"F","0","0","hrm:project:remove","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1110,"查看执行历史详情",1066,9,"",null,null,1,0,"F","0","0","hrm:history:detail","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1111,"删除执行历史",1066,10,"",null,null,1,0,"F","0","0","hrm:history:delete","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1112,"查看执行历史详情",1081,7,"",null,null,1,0,"F","0","0","hrm:history:detail","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1113,"删除执行历史",1081,9,"",null,null,1,0,"F","0","0","hrm:history:delete","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1114,"用例执行",1063,4,"",null,null,1,0,"F","0","0","hrm:case:run","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1115,"新增",1084,1,"",null,null,1,0,"F","0","0","qtr:suite:add","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1116,"运行",1084,2,"",null,null,1,0,"F","0","0","hrm:case:run","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1117,"修改",1084,3,"",null,null,1,0,"F","0","0","qtr:suite:edit","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1118,"配置",1084,4,"",null,null,1,0,"F","0","0","qtr:suite:edit","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1119,"删除",1084,5,"",null,null,1,0,"F","0","0","qtr:suite:remove","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1123,"新增",1085,1,"",null,null,1,0,"F","0","0","qtr:job:add","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1128,"编辑",1085,2,"",null,null,1,0,"F","0","0","qtr:job:edit","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1133,"删除",1085,3,"",null,null,1,0,"F","0","0","qtr:job:remove","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1138,"导出",1085,4,"",null,null,1,0,"F","0","0","qtr:job:export","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1143,"日志",1085,5,"",null,null,1,0,"F","0","0","qtr:job:query","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1148,"执行",1085,6,"",null,null,1,0,"F","0","0","qtr:job:changeStatus","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1153,"环境管理",1061,7,"hrm",null,null,1,0,"M","0","0",null,"size","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1158,"Agent管理",1153,2,"agent","hrm/agent/index",null,1,0,"C","0","0","qtr:agent:list","druid","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1163,"转发管理",1153,3,"forwarding","hrm/forward/index",null,1,0,"C","0","0","qtr:forwardRules:list","code","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1168,"编辑",1158,1,"",null,null,1,0,"F","0","0","qtr:agent:edit","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1173,"删除",1158,2,"",null,null,1,0,"F","0","0","qtr:agent:remove","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1178,"新增",1163,1,"",null,null,1,0,"F","0","0","qtr:forwardRules:add","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1183,"编辑",1163,2,"",null,null,1,0,"F","0","0","qtr:forwardRules:edit","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1188,"删除",1163,3,"",null,null,1,0,"F","0","0","qtr:forwardRules:remove","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1193,"复制",1163,4,"",null,null,1,0,"F","0","0","qtr:forwardRules:copy","#","admin",sysdate(),"admin",null,"");
INSERT INTO sys_menu VALUES (1198,"详情",1163,5,"",null,null,1,0,"F","0","0","qtr:forwardRules:detail","#","admin",sysdate(),"admin",null,"");

-- ----------------------------
-- 6、用户和角色关联表  用户N-1角色
-- ----------------------------
drop table if exists sys_user_role;
create table sys_user_role (
  user_id   bigint(20) not null comment '用户ID',
  role_id   bigint(20) not null comment '角色ID',
  primary key(user_id, role_id)
) engine=innodb comment = '用户和角色关联表';

-- ----------------------------
-- 初始化-用户和角色关联表数据
-- ----------------------------
insert into sys_user_role values ('1', '1');
insert into sys_user_role values ('2', '2');


-- ----------------------------
-- 7、角色和菜单关联表  角色1-N菜单
-- ----------------------------
drop table if exists sys_role_menu;
create table sys_role_menu (
  role_id   bigint(20) not null comment '角色ID',
  menu_id   bigint(20) not null comment '菜单ID',
  primary key(role_id, menu_id)
) engine=innodb comment = '角色和菜单关联表';

-- ----------------------------
-- 初始化-角色和菜单关联表数据
-- ----------------------------
insert into sys_role_menu values ('2', '1');
insert into sys_role_menu values ('2', '2');
insert into sys_role_menu values ('2', '3');
insert into sys_role_menu values ('2', '4');
insert into sys_role_menu values ('2', '100');
insert into sys_role_menu values ('2', '101');
insert into sys_role_menu values ('2', '102');
insert into sys_role_menu values ('2', '103');
insert into sys_role_menu values ('2', '104');
insert into sys_role_menu values ('2', '105');
insert into sys_role_menu values ('2', '106');
insert into sys_role_menu values ('2', '107');
insert into sys_role_menu values ('2', '108');
insert into sys_role_menu values ('2', '109');
insert into sys_role_menu values ('2', '110');
insert into sys_role_menu values ('2', '111');
insert into sys_role_menu values ('2', '112');
insert into sys_role_menu values ('2', '113');
insert into sys_role_menu values ('2', '114');
insert into sys_role_menu values ('2', '115');
insert into sys_role_menu values ('2', '116');
insert into sys_role_menu values ('2', '117');
insert into sys_role_menu values ('2', '500');
insert into sys_role_menu values ('2', '501');
insert into sys_role_menu values ('2', '1000');
insert into sys_role_menu values ('2', '1001');
insert into sys_role_menu values ('2', '1002');
insert into sys_role_menu values ('2', '1003');
insert into sys_role_menu values ('2', '1004');
insert into sys_role_menu values ('2', '1005');
insert into sys_role_menu values ('2', '1006');
insert into sys_role_menu values ('2', '1007');
insert into sys_role_menu values ('2', '1008');
insert into sys_role_menu values ('2', '1009');
insert into sys_role_menu values ('2', '1010');
insert into sys_role_menu values ('2', '1011');
insert into sys_role_menu values ('2', '1012');
insert into sys_role_menu values ('2', '1013');
insert into sys_role_menu values ('2', '1014');
insert into sys_role_menu values ('2', '1015');
insert into sys_role_menu values ('2', '1016');
insert into sys_role_menu values ('2', '1017');
insert into sys_role_menu values ('2', '1018');
insert into sys_role_menu values ('2', '1019');
insert into sys_role_menu values ('2', '1020');
insert into sys_role_menu values ('2', '1021');
insert into sys_role_menu values ('2', '1022');
insert into sys_role_menu values ('2', '1023');
insert into sys_role_menu values ('2', '1024');
insert into sys_role_menu values ('2', '1025');
insert into sys_role_menu values ('2', '1026');
insert into sys_role_menu values ('2', '1027');
insert into sys_role_menu values ('2', '1028');
insert into sys_role_menu values ('2', '1029');
insert into sys_role_menu values ('2', '1030');
insert into sys_role_menu values ('2', '1031');
insert into sys_role_menu values ('2', '1032');
insert into sys_role_menu values ('2', '1033');
insert into sys_role_menu values ('2', '1034');
insert into sys_role_menu values ('2', '1035');
insert into sys_role_menu values ('2', '1036');
insert into sys_role_menu values ('2', '1037');
insert into sys_role_menu values ('2', '1038');
insert into sys_role_menu values ('2', '1039');
insert into sys_role_menu values ('2', '1040');
insert into sys_role_menu values ('2', '1041');
insert into sys_role_menu values ('2', '1042');
insert into sys_role_menu values ('2', '1043');
insert into sys_role_menu values ('2', '1044');
insert into sys_role_menu values ('2', '1045');
insert into sys_role_menu values ('2', '1046');
insert into sys_role_menu values ('2', '1047');
insert into sys_role_menu values ('2', '1048');
insert into sys_role_menu values ('2', '1049');
insert into sys_role_menu values ('2', '1050');
insert into sys_role_menu values ('2', '1051');
insert into sys_role_menu values ('2', '1052');
insert into sys_role_menu values ('2', '1053');
insert into sys_role_menu values ('2', '1054');
insert into sys_role_menu values ('2', '1055');
insert into sys_role_menu values ('2', '1056');
insert into sys_role_menu values ('2', '1057');
insert into sys_role_menu values ('2', '1058');
insert into sys_role_menu values ('2', '1059');
insert into sys_role_menu values ('2', '1060');

-- ----------------------------
-- 8、角色和部门关联表  角色1-N部门
-- ----------------------------
drop table if exists sys_role_dept;
create table sys_role_dept (
  role_id   bigint(20) not null comment '角色ID',
  dept_id   bigint(20) not null comment '部门ID',
  primary key(role_id, dept_id)
) engine=innodb comment = '角色和部门关联表';

-- ----------------------------
-- 初始化-角色和部门关联表数据
-- ----------------------------
insert into sys_role_dept values ('2', '100');
insert into sys_role_dept values ('2', '101');
insert into sys_role_dept values ('2', '105');


-- ----------------------------
-- 9、用户与岗位关联表  用户1-N岗位
-- ----------------------------
drop table if exists sys_user_post;
create table sys_user_post
(
  user_id   bigint(20) not null comment '用户ID',
  post_id   bigint(20) not null comment '岗位ID',
  primary key (user_id, post_id)
) engine=innodb comment = '用户与岗位关联表';

-- ----------------------------
-- 初始化-用户与岗位关联表数据
-- ----------------------------
insert into sys_user_post values ('1', '1');
insert into sys_user_post values ('2', '2');


-- ----------------------------
-- 10、操作日志记录
-- ----------------------------
drop table if exists sys_oper_log;
create table sys_oper_log (
  oper_id           bigint(20)      not null auto_increment    comment '日志主键',
  title             varchar(50)     default ''                 comment '模块标题',
  business_type     int(2)          default 0                  comment '业务类型（0其它 1新增 2修改 3删除）',
  method            varchar(100)    default ''                 comment '方法名称',
  request_method    varchar(10)     default ''                 comment '请求方式',
  operator_type     int(1)          default 0                  comment '操作类别（0其它 1后台用户 2手机端用户）',
  oper_name         varchar(50)     default ''                 comment '操作人员',
  dept_name         varchar(50)     default ''                 comment '部门名称',
  oper_url          varchar(255)    default ''                 comment '请求URL',
  oper_ip           varchar(128)    default ''                 comment '主机地址',
  oper_location     varchar(255)    default ''                 comment '操作地点',
  oper_param        varchar(2000)   default ''                 comment '请求参数',
  json_result       varchar(2000)   default ''                 comment '返回参数',
  status            int(1)          default 0                  comment '操作状态（0正常 1异常）',
  error_msg         varchar(2000)   default ''                 comment '错误消息',
  oper_time         datetime                                   comment '操作时间',
  cost_time         bigint(20)      default 0                  comment '消耗时间',
  primary key (oper_id),
  key idx_sys_oper_log_bt (business_type),
  key idx_sys_oper_log_s  (status),
  key idx_sys_oper_log_ot (oper_time)
) engine=innodb auto_increment=100 comment = '操作日志记录';


-- ----------------------------
-- 11、字典类型表
-- ----------------------------
drop table if exists sys_dict_type;
create table sys_dict_type
(
  dict_id          bigint(20)      not null auto_increment    comment '字典主键',
  dict_name        varchar(100)    default ''                 comment '字典名称',
  dict_type        varchar(100)    default ''                 comment '字典类型',
  status           char(1)         default '0'                comment '状态（0正常 1停用）',
  create_by        varchar(64)     default ''                 comment '创建者',
  create_time      datetime                                   comment '创建时间',
  update_by        varchar(64)     default ''                 comment '更新者',
  update_time      datetime                                   comment '更新时间',
  remark           varchar(500)    default null               comment '备注',
  primary key (dict_id),
  unique (dict_type)
) engine=innodb auto_increment=100 comment = '字典类型表';

INSERT INTO `sys_dict_type` VALUES (1,"用户性别","sys_user_sex","0","admin",sysdate(),"",null,"用户性别列表");
INSERT INTO `sys_dict_type` VALUES (2,"菜单状态","sys_show_hide","0","admin",sysdate(),"",null,"菜单状态列表");
INSERT INTO `sys_dict_type` VALUES (3,"系统开关","sys_normal_disable","0","admin",sysdate(),"",null,"系统开关列表");
INSERT INTO `sys_dict_type` VALUES (4,"任务状态","sys_job_status","0","admin",sysdate(),"",null,"任务状态列表");
INSERT INTO `sys_dict_type` VALUES (5,"任务分组","sys_job_group","0","admin",sysdate(),"",null,"任务分组列表");
INSERT INTO `sys_dict_type` VALUES (6,"任务执行器","sys_job_executor","0","admin",sysdate(),"",null,"任务执行器列表");
INSERT INTO `sys_dict_type` VALUES (7,"系统是否","sys_yes_no","0","admin",sysdate(),"",null,"系统是否列表");
INSERT INTO `sys_dict_type` VALUES (8,"通知类型","sys_notice_type","0","admin",sysdate(),"",null,"通知类型列表");
INSERT INTO `sys_dict_type` VALUES (9,"通知状态","sys_notice_status","0","admin",sysdate(),"",null,"通知状态列表");
INSERT INTO `sys_dict_type` VALUES (10,"操作类型","sys_oper_type","0","admin",sysdate(),"",null,"操作类型列表");
INSERT INTO `sys_dict_type` VALUES (11,"系统状态","sys_common_status","0","admin",sysdate(),"",null,"登录状态列表");
INSERT INTO `sys_dict_type` VALUES (12,"请求类型","sys_request_method","0","admin",sysdate(),"",null,"支持的请求类型");
INSERT INTO `sys_dict_type` VALUES (13,"hrm数据支持的数据类型","hrm_data_type","0","admin",sysdate(),"",null,"hrm数据支持的数据类型，例如变量、参数的data和param");
INSERT INTO `sys_dict_type` VALUES (14,"hrm用例执行结果","hrm_run_status","0","admin",sysdate(),"",null,"用例及api执行结果");
INSERT INTO `sys_dict_type` VALUES (15,"qtr任务执行器","qtr_job_executor","0","admin",sysdate(),"",null,"qtr任务执行器列表");
INSERT INTO `sys_dict_type` VALUES (16,"qtr任务分组","qtr_job_group","0","admin",sysdate(),"",null,"qtr任务分组列表");
INSERT INTO `sys_dict_type` VALUES (17,"qtr任务状态","qtr_job_status","0","admin",sysdate(),"",null,"qtr任务状态列表");
INSERT INTO `sys_dict_type` VALUES (18,"用例执行方式","hrm_run_way","0","admin",sysdate(),"",null,"");
INSERT INTO `sys_dict_type` VALUES (19,"hrm用例状态","qtr_case_status","0","admin",sysdate(),"",null,"");
INSERT INTO `sys_dict_type` VALUES (20,"qtr数据状态","qtr_data_status","0","admin",sysdate(),"",null,"");
INSERT INTO `sys_dict_type` VALUES (21,"qtr数据类型枚举","qtr_data_type","0","admin",sysdate(),"",null,"");
INSERT INTO `sys_dict_type` VALUES (22,"任务执行状态","job_run_status","0","admin",sysdate(),"",null,"");



-- ----------------------------
-- 12、字典数据表
-- ----------------------------
drop table if exists sys_dict_data;
create table sys_dict_data
(
  dict_code        bigint(20)      not null auto_increment    comment '字典编码',
  dict_sort        int(4)          default 0                  comment '字典排序',
  dict_label       varchar(100)    default ''                 comment '字典标签',
  dict_value       varchar(100)    default ''                 comment '字典键值',
  dict_type        varchar(100)    default ''                 comment '字典类型',
  css_class        varchar(100)    default null               comment '样式属性（其他样式扩展）',
  list_class       varchar(100)    default null               comment '表格回显样式',
  is_default       char(1)         default 'N'                comment '是否默认（Y是 N否）',
  status           char(1)         default '0'                comment '状态（0正常 1停用）',
  create_by        varchar(64)     default ''                 comment '创建者',
  create_time      datetime                                   comment '创建时间',
  update_by        varchar(64)     default ''                 comment '更新者',
  update_time      datetime                                   comment '更新时间',
  remark           varchar(500)    default null               comment '备注',
  primary key (dict_code)
) engine=innodb auto_increment=100 comment = '字典数据表';

insert into sys_dict_data values(1,  1,  '男',       '0',           'sys_user_sex',        '',   '',        'Y', '0', 'admin', sysdate(), '', null, '性别男');
insert into sys_dict_data values(2,  2,  '女',       '1',           'sys_user_sex',        '',   '',        'N', '0', 'admin', sysdate(), '', null, '性别女');
insert into sys_dict_data values(3,  3,  '未知',     '2',           'sys_user_sex',        '',   '',        'N', '0', 'admin', sysdate(), '', null, '性别未知');
insert into sys_dict_data values(4,  1,  '显示',     '0',           'sys_show_hide',       '',   'primary', 'Y', '0', 'admin', sysdate(), '', null, '显示菜单');
insert into sys_dict_data values(5,  2,  '隐藏',     '1',           'sys_show_hide',       '',   'danger',  'N', '0', 'admin', sysdate(), '', null, '隐藏菜单');
insert into sys_dict_data values(6,  1,  '正常',     '0',           'sys_normal_disable',  '',   'primary', 'Y', '0', 'admin', sysdate(), '', null, '正常状态');
insert into sys_dict_data values(7,  2,  '停用',     '1',           'sys_normal_disable',  '',   'danger',  'N', '0', 'admin', sysdate(), '', null, '停用状态');
insert into sys_dict_data values(8,  1,  '正常',     '0',           'sys_job_status',      '',   'primary', 'Y', '0', 'admin', sysdate(), '', null, '正常状态');
insert into sys_dict_data values(9,  2,  '暂停',     '1',           'sys_job_status',      '',   'danger',  'N', '0', 'admin', sysdate(), '', null, '停用状态');
insert into sys_dict_data values(10, 1,  '默认',     'default',     'sys_job_group',       '',   '',        'Y', '0', 'admin', sysdate(), '', null, '默认分组');
insert into sys_dict_data values(11, 2,  '数据库',   'sqlalchemy',  'sys_job_group',       '',   '',        'N', '0', 'admin', sysdate(), '', null, '数据库分组');
insert into sys_dict_data values(12, 3,  'redis',    'redis',  			'sys_job_group',       '',   '',        'N', '0', 'admin', sysdate(), '', null, 'reids分组');
insert into sys_dict_data values(13, 1,  '默认',     'default',  		'sys_job_executor',    '',   '',        'N', '0', 'admin', sysdate(), '', null, '线程池');
insert into sys_dict_data values(14, 2,  '进程池',   'processpool', 'sys_job_executor',    '',   '',        'N', '0', 'admin', sysdate(), '', null, '进程池');
insert into sys_dict_data values(15, 1,  '是',       'Y',       		'sys_yes_no',          '',   'primary', 'Y', '0', 'admin', sysdate(), '', null, '系统默认是');
insert into sys_dict_data values(16, 2,  '否',       'N',       		'sys_yes_no',          '',   'danger',  'N', '0', 'admin', sysdate(), '', null, '系统默认否');
insert into sys_dict_data values(17, 1,  '通知',     '1',       		'sys_notice_type',     '',   'warning', 'Y', '0', 'admin', sysdate(), '', null, '通知');
insert into sys_dict_data values(18, 2,  '公告',     '2',       		'sys_notice_type',     '',   'success', 'N', '0', 'admin', sysdate(), '', null, '公告');
insert into sys_dict_data values(19, 1,  '正常',     '0',       		'sys_notice_status',   '',   'primary', 'Y', '0', 'admin', sysdate(), '', null, '正常状态');
insert into sys_dict_data values(20, 2,  '关闭',     '1',       		'sys_notice_status',   '',   'danger',  'N', '0', 'admin', sysdate(), '', null, '关闭状态');
insert into sys_dict_data values(21, 99, '其他',     '0',       		'sys_oper_type',       '',   'info',    'N', '0', 'admin', sysdate(), '', null, '其他操作');
insert into sys_dict_data values(22, 1,  '新增',     '1',       		'sys_oper_type',       '',   'info',    'N', '0', 'admin', sysdate(), '', null, '新增操作');
insert into sys_dict_data values(23, 2,  '修改',     '2',       		'sys_oper_type',       '',   'info',    'N', '0', 'admin', sysdate(), '', null, '修改操作');
insert into sys_dict_data values(24, 3,  '删除',     '3',       		'sys_oper_type',       '',   'danger',  'N', '0', 'admin', sysdate(), '', null, '删除操作');
insert into sys_dict_data values(25, 4,  '授权',     '4',       		'sys_oper_type',       '',   'primary', 'N', '0', 'admin', sysdate(), '', null, '授权操作');
insert into sys_dict_data values(26, 5,  '导出',     '5',       		'sys_oper_type',       '',   'warning', 'N', '0', 'admin', sysdate(), '', null, '导出操作');
insert into sys_dict_data values(27, 6,  '导入',     '6',       		'sys_oper_type',       '',   'warning', 'N', '0', 'admin', sysdate(), '', null, '导入操作');
insert into sys_dict_data values(28, 7,  '强退',     '7',       		'sys_oper_type',       '',   'danger',  'N', '0', 'admin', sysdate(), '', null, '强退操作');
insert into sys_dict_data values(29, 8,  '生成代码', '8',       		'sys_oper_type',       '',   'warning', 'N', '0', 'admin', sysdate(), '', null, '生成操作');
insert into sys_dict_data values(30, 9,  '清空数据', '9',       		'sys_oper_type',       '',   'danger',  'N', '0', 'admin', sysdate(), '', null, '清空操作');
insert into sys_dict_data values(31, 1,  '成功',     '0',       		'sys_common_status',   '',   'primary', 'N', '0', 'admin', sysdate(), '', null, '正常状态');
insert into sys_dict_data values(32, 2,  '失败',     '1',       		'sys_common_status',   '',   'danger',  'N', '0', 'admin', sysdate(), '', null, '停用状态');
INSERT INTO sys_dict_data VALUES(33,0,"GET","GET","sys_request_method","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(34,1,"POST","POST","sys_request_method","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(35,2,"PUT","PUT","sys_request_method","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(36,3,"DELETE","DELETE","sys_request_method","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(37,0,"string","string","hrm_data_type","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(38,1,"int","int","hrm_data_type","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(39,2,"boolean","boolean","hrm_data_type","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(40,3,"float","float","hrm_data_type","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(41,4,"json","json","hrm_data_type","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(42,5,"any","any","hrm_data_type","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(43,0,"成功","1","hrm_run_status","","success","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(44,1,"失败","2","hrm_run_status","","danger","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(45,2,"跳过","3","hrm_run_status","","info","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(46,1,"正常","0","qtr_job_status","","primary","N","0","admin",sysdate(),"admin",null,"正常状态");
INSERT INTO sys_dict_data VALUES(47,2,"暂停","1","qtr_job_status","","danger","N","0","admin",sysdate(),"admin",null,"暂停状态");
INSERT INTO sys_dict_data VALUES(48,1,"默认","default","qtr_job_group","","default","N","0","admin",sysdate(),"admin",null,"默认分组");
INSERT INTO sys_dict_data VALUES(49,2,"数据库","sqlalchemy","qtr_job_group","","default","N","0","admin",sysdate(),"admin",null,"数据库分组");
INSERT INTO sys_dict_data VALUES(50,3,"redis","redis","qtr_job_group","","default","N","0","admin",sysdate(),"admin",null,"redis分组");
INSERT INTO sys_dict_data VALUES(51,1,"默认","default","qtr_job_executor","","default","N","0","admin",sysdate(),"admin",null,"线程池");
INSERT INTO sys_dict_data VALUES(52,2,"进程池","processpool","qtr_job_executor","","default","N","0","admin",sysdate(),"admin",null,"进程池");
INSERT INTO sys_dict_data VALUES(53,0,"CaseRun","1","hrm_run_way","","success","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(54,0,"CaseDebug","32","hrm_run_way","","primary","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(55,0,"Api","16","hrm_run_way","","warning","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(58,0,"正常","2","qtr_case_status","","success","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(63,1,"停用","1","qtr_case_status","","danger","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(68,2,"跳过","4","qtr_case_status","","info","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(73,3,"标记失败","8","qtr_case_status","","warning","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(78,4,"标记通过","16","qtr_case_status","","primary","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(83,0,"ModelRun","2","hrm_run_way","","success","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(88,0,"SuiteRun","4","hrm_run_way","","success","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(93,0,"ProjectRun","8","hrm_run_way","","success","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(98,4,"标记失败","5","hrm_run_status","","warning","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(103,3,"标记通过","6","hrm_run_status","","primary","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(108,0,"正常","2","qtr_data_status","","success","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(113,1,"停用","1","qtr_data_status","","danger","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(118,0,"项目","1","qtr_data_type","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(123,0,"模块","2","qtr_data_type","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(128,0,"用例","3","qtr_data_type","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(133,0,"配置","4","qtr_data_type","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(138,0,"套件","5","qtr_data_type","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(143,0,"报告","6","qtr_data_type","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(148,0,"环境配置","7","qtr_data_type","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(153,0,"debugtalk","8","qtr_data_type","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(158,0,"任务","9","qtr_data_type","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(163,0,"接口","10","qtr_data_type","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(168,0,"文件夹","11","qtr_data_type","","default","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(173,0,"执行中","1","job_run_status","","primary","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(178,0,"并发限制","2","job_run_status","","warning","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(183,0,"成功","3","job_run_status","","success","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(188,0,"异常","4","job_run_status","","danger","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(193,0,"错过时间","5","job_run_status","","warning","N","0","admin",sysdate(),"admin",null,"");
INSERT INTO sys_dict_data VALUES(198,0,"未开始","6","job_run_status","","info","N","0","admin",sysdate(),"admin",null,"");


-- ----------------------------
-- 13、参数配置表
-- ----------------------------
drop table if exists sys_config;
create table sys_config (
  config_id         int(5)          not null auto_increment    comment '参数主键',
  config_name       varchar(100)    default ''                 comment '参数名称',
  config_key        varchar(100)    default ''                 comment '参数键名',
  config_value      varchar(500)    default ''                 comment '参数键值',
  config_type       char(1)         default 'N'                comment '系统内置（Y是 N否）',
  create_by         varchar(64)     default ''                 comment '创建者',
  create_time       datetime                                   comment '创建时间',
  update_by         varchar(64)     default ''                 comment '更新者',
  update_time       datetime                                   comment '更新时间',
  remark            varchar(500)    default null               comment '备注',
  primary key (config_id)
) engine=innodb auto_increment=100 comment = '参数配置表';

insert into sys_config values(1, '主框架页-默认皮肤样式名称',     'sys.index.skinName',            'skin-blue',     'Y', 'admin', sysdate(), '', null, '蓝色 skin-blue、绿色 skin-green、紫色 skin-purple、红色 skin-red、黄色 skin-yellow' );
insert into sys_config values(2, '用户管理-账号初始密码',         'sys.user.initPassword',         '123456',        'Y', 'admin', sysdate(), '', null, '初始化密码 123456' );
insert into sys_config values(3, '主框架页-侧边栏主题',           'sys.index.sideTheme',           'theme-dark',    'Y', 'admin', sysdate(), '', null, '深色主题theme-dark，浅色主题theme-light' );
insert into sys_config values(4, '账号自助-验证码开关',           'sys.account.captchaEnabled',    'true',          'Y', 'admin', sysdate(), '', null, '是否开启验证码功能（true开启，false关闭）');
insert into sys_config values(5, '账号自助-是否开启用户注册功能', 'sys.account.registerUser',      'false',         'Y', 'admin', sysdate(), '', null, '是否开启注册用户功能（true开启，false关闭）');
insert into sys_config values(6, '用户登录-黑名单列表',           'sys.login.blackIPList',         '',              'Y', 'admin', sysdate(), '', null, '设置登录IP黑名单限制，多个匹配项以;分隔，支持匹配（*通配、网段）');


-- ----------------------------
-- 14、系统访问记录
-- ----------------------------
drop table if exists sys_logininfor;
create table sys_logininfor (
  info_id        bigint(20)     not null auto_increment   comment '访问ID',
  user_name      varchar(50)    default ''                comment '用户账号',
  ipaddr         varchar(128)   default ''                comment '登录IP地址',
  login_location varchar(255)   default ''                comment '登录地点',
  browser        varchar(50)    default ''                comment '浏览器类型',
  os             varchar(50)    default ''                comment '操作系统',
  status         char(1)        default '0'               comment '登录状态（0成功 1失败）',
  msg            varchar(255)   default ''                comment '提示消息',
  login_time     datetime                                 comment '访问时间',
  primary key (info_id),
  key idx_sys_logininfor_s  (status),
  key idx_sys_logininfor_lt (login_time)
) engine=innodb auto_increment=100 comment = '系统访问记录';


-- ----------------------------
-- 15、定时任务调度表
-- ----------------------------
drop table if exists sys_job;
create table sys_job (
  job_id              bigint(20)    not null auto_increment    comment '任务ID',
  job_name            varchar(64)   default ''                 comment '任务名称',
  job_group           varchar(64)   default 'default'          comment '任务组名',
	job_executor 				varchar(64)   default 'default' 				 comment '任务执行器',
  invoke_target       varchar(500)  not null                   comment '调用目标字符串',
  job_args						varchar(255)	default ''								 comment '位置参数',
  job_kwargs					varchar(255)	default ''								 comment '关键字参数',
  cron_expression     varchar(255)  default ''                 comment 'cron执行表达式',
  misfire_policy      varchar(20)   default '3'                comment '计划执行错误策略（1立即执行 2执行一次 3放弃执行）',
  concurrent          char(1)       default '1'                comment '是否并发执行（0允许 1禁止）',
  status              char(1)       default '0'                comment '状态（0正常 1暂停）',
  create_by           varchar(64)   default ''                 comment '创建者',
  create_time         datetime                                 comment '创建时间',
  update_by           varchar(64)   default ''                 comment '更新者',
  update_time         datetime                                 comment '更新时间',
  remark              varchar(500)  default ''                 comment '备注信息',
  primary key (job_id, job_name, job_group)
) engine=innodb auto_increment=100 comment = '定时任务调度表';

insert into sys_job values(1, '系统默认（无参）', 'default', 'default', 'module_task.scheduler_test.job', NULL,   NULL, '0/10 * * * * ?', '3', '1', '1', 'admin', sysdate(), '', null, '');
insert into sys_job values(2, '系统默认（有参）', 'default', 'default', 'module_task.scheduler_test.job', 'test', NULL, '0/15 * * * * ?', '3', '1', '1', 'admin', sysdate(), '', null, '');
insert into sys_job values(3, '系统默认（多参）', 'default', 'default', 'module_task.scheduler_test.job', 'new',  '{\"test\": 111}', '0/20 * * * * ?', '3', '1', '1', 'admin', sysdate(), '', null, '');


-- ----------------------------
-- 16、定时任务调度日志表
-- ----------------------------
drop table if exists sys_job_log;
create table sys_job_log (
  job_log_id          bigint(20)     not null auto_increment    comment '任务日志ID',
  job_name            varchar(64)    not null                   comment '任务名称',
  job_group           varchar(64)    not null                   comment '任务组名',
  job_executor				varchar(64)		 not null										comment '任务执行器',
  invoke_target       varchar(500)   not null                   comment '调用目标字符串',
  job_args						varchar(255)	 default ''									comment '位置参数',
  job_kwargs					varchar(255)	 default ''									comment '关键字参数',
  job_trigger					varchar(255)	 default ''									comment '任务触发器',
  job_message         varchar(500)                              comment '日志信息',
  status              char(1)        default '0'                comment '执行状态（0正常 1失败）',
  exception_info      varchar(2000)  default ''                 comment '异常信息',
  create_time         datetime                                  comment '创建时间',
  primary key (job_log_id)
) engine=innodb comment = '定时任务调度日志表';


-- ----------------------------
-- 17、通知公告表
-- ----------------------------
drop table if exists sys_notice;
create table sys_notice (
  notice_id         int(4)          not null auto_increment    comment '公告ID',
  notice_title      varchar(50)     not null                   comment '公告标题',
  notice_type       char(1)         not null                   comment '公告类型（1通知 2公告）',
  notice_content    longblob        default null               comment '公告内容',
  status            char(1)         default '0'                comment '公告状态（0正常 1关闭）',
  create_by         varchar(64)     default ''                 comment '创建者',
  create_time       datetime                                   comment '创建时间',
  update_by         varchar(64)     default ''                 comment '更新者',
  update_time       datetime                                   comment '更新时间',
  remark            varchar(255)    default null               comment '备注',
  primary key (notice_id)
) engine=innodb auto_increment=10 comment = '通知公告表';

-- ----------------------------
-- 初始化-公告信息表数据
-- ----------------------------
insert into sys_notice values('1', '温馨提醒：2018-07-01 vfadmin新版本发布啦', '2', '新版本内容', '0', 'admin', sysdate(), '', null, '管理员');
insert into sys_notice values('2', '维护通知：2018-07-01 vfadmin系统凌晨维护', '1', '维护内容',   '0', 'admin', sysdate(), '', null, '管理员');


-- ----------------------------
-- 18、代码生成业务表
-- ----------------------------
drop table if exists gen_table;
create table gen_table (
  table_id          bigint(20)      not null auto_increment    comment '编号',
  table_name        varchar(200)    default ''                 comment '表名称',
  table_comment     varchar(500)    default ''                 comment '表描述',
  sub_table_name    varchar(64)     default null               comment '关联子表的表名',
  sub_table_fk_name varchar(64)     default null               comment '子表关联的外键名',
  class_name        varchar(100)    default ''                 comment '实体类名称',
  tpl_category      varchar(200)    default 'crud'             comment '使用的模板（crud单表操作 tree树表操作）',
  tpl_web_type      varchar(30)     default ''                 comment '前端模板类型（element-ui模版 element-plus模版）',
  package_name      varchar(100)                               comment '生成包路径',
  module_name       varchar(30)                                comment '生成模块名',
  business_name     varchar(30)                                comment '生成业务名',
  function_name     varchar(50)                                comment '生成功能名',
  function_author   varchar(50)                                comment '生成功能作者',
  gen_type          char(1)         default '0'                comment '生成代码方式（0zip压缩包 1自定义路径）',
  gen_path          varchar(200)    default '/'                comment '生成路径（不填默认项目路径）',
  options           varchar(1000)                              comment '其它生成选项',
  create_by         varchar(64)     default ''                 comment '创建者',
  create_time 	    datetime                                   comment '创建时间',
  update_by         varchar(64)     default ''                 comment '更新者',
  update_time       datetime                                   comment '更新时间',
  remark            varchar(500)    default null               comment '备注',
  primary key (table_id)
) engine=innodb auto_increment=1 comment = '代码生成业务表';


-- ----------------------------
-- 19、代码生成业务表字段
-- ----------------------------
drop table if exists gen_table_column;
create table gen_table_column (
  column_id         bigint(20)      not null auto_increment    comment '编号',
  table_id          bigint(20)                                 comment '归属表编号',
  column_name       varchar(200)                               comment '列名称',
  column_comment    varchar(500)                               comment '列描述',
  column_type       varchar(100)                               comment '列类型',
  java_type         varchar(500)                               comment 'JAVA类型',
  java_field        varchar(200)                               comment 'JAVA字段名',
  is_pk             char(1)                                    comment '是否主键（1是）',
  is_increment      char(1)                                    comment '是否自增（1是）',
  is_required       char(1)                                    comment '是否必填（1是）',
  is_insert         char(1)                                    comment '是否为插入字段（1是）',
  is_edit           char(1)                                    comment '是否编辑字段（1是）',
  is_list           char(1)                                    comment '是否列表字段（1是）',
  is_query          char(1)                                    comment '是否查询字段（1是）',
  query_type        varchar(200)    default 'EQ'               comment '查询方式（等于、不等于、大于、小于、范围）',
  html_type         varchar(200)                               comment '显示类型（文本框、文本域、下拉框、复选框、单选框、日期控件）',
  dict_type         varchar(200)    default ''                 comment '字典类型',
  sort              int                                        comment '排序',
  create_by         varchar(64)     default ''                 comment '创建者',
  create_time 	    datetime                                   comment '创建时间',
  update_by         varchar(64)     default ''                 comment '更新者',
  update_time       datetime                                   comment '更新时间',
  primary key (column_id)
) engine=innodb auto_increment=1 comment = '代码生成业务表字段';