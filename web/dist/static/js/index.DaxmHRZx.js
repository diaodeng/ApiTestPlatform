import{X as V,r as v,J as fe,N as ce,d,H as K,o as p,c as q,I as h,M as _e,h as n,e as l,f as t,l as ve,O,P as Q,m as g,p as m,K as j,i as H,y as J,n as P,F as ge,s as ye,L as be}from"./index.DgyczuKs.js";function M(r){return V({url:"/system/dept/list",method:"get",params:r})}function he(r){return V({url:"/system/dept/list/exclude/"+r,method:"get"})}function Ve(r){return V({url:"/system/dept/"+r,method:"get"})}function ke(r){return V({url:"/system/dept",method:"post",data:r})}function we(r){return V({url:"/system/dept",method:"put",data:r})}function Ne(r){return V({url:"/system/dept/"+r,method:"delete"})}const Ie={class:"app-container"},Ce={class:"dialog-footer"},xe=ge({name:"Dept"}),Ue=Object.assign(xe,{setup(r){const{proxy:s}=ye(),{sys_normal_disable:C}=s.useDict("sys_normal_disable"),E=v([]),_=v(!1),x=v(!0),N=v(!0),D=v(""),U=v([]),S=v(!0),T=v(!0),X=fe({form:{},queryParams:{deptName:void 0,status:void 0},rules:{parentId:[{required:!0,message:"上级部门不能为空",trigger:"blur"}],deptName:[{required:!0,message:"部门名称不能为空",trigger:"blur"}],orderNum:[{required:!0,message:"显示排序不能为空",trigger:"blur"}],email:[{type:"email",message:"请输入正确的邮箱地址",trigger:["blur","change"]}],phone:[{pattern:/^1[3|4|5|6|7|8|9][0-9]\d{8}$/,message:"请输入正确的手机号码",trigger:"blur"}]}}),{queryParams:y,form:o,rules:z}=ce(X);function b(){x.value=!0,M(y.value).then(u=>{E.value=s.handleTree(u.data,"deptId"),x.value=!1})}function G(){_.value=!1,$()}function $(){o.value={deptId:void 0,parentId:void 0,deptName:void 0,orderNum:0,leader:void 0,phone:void 0,email:void 0,status:"0"},s.resetForm("deptRef")}function R(){b()}function W(){s.resetForm("queryRef"),R()}function F(u){$(),M().then(e=>{U.value=s.handleTree(e.data,"deptId")}),u!=null&&(o.value.parentId=u.deptId),_.value=!0,D.value="添加部门"}function Y(){T.value=!1,S.value=!S.value,be(()=>{T.value=!0})}function Z(u){$(),he(u.deptId).then(e=>{U.value=s.handleTree(e.data,"deptId")}),Ve(u.deptId).then(e=>{o.value=e.data,_.value=!0,D.value="修改部门"})}function ee(){s.$refs.deptRef.validate(u=>{u&&(o.value.deptId!=null?we(o.value).then(e=>{s.$modal.msgSuccess("修改成功"),_.value=!1,b()}):ke(o.value).then(e=>{s.$modal.msgSuccess("新增成功"),_.value=!1,b()}))})}function le(u){s.$modal.confirm('是否确认删除名称为"'+u.deptName+'"的数据项?').then(function(){return Ne(u.deptId)}).then(()=>{b(),s.$modal.msgSuccess("删除成功")}).catch(()=>{})}return b(),(u,e)=>{const k=d("el-input"),i=d("el-form-item"),te=d("el-option"),ae=d("el-select"),f=d("el-button"),B=d("el-form"),c=d("el-col"),ne=d("right-toolbar"),L=d("el-row"),w=d("el-table-column"),oe=d("dict-tag"),de=d("el-table"),ue=d("el-tree-select"),re=d("el-input-number"),se=d("el-radio"),pe=d("el-radio-group"),ie=d("el-dialog"),I=K("hasPermi"),me=K("loading");return p(),q("div",Ie,[h(l(B,{model:n(y),ref:"queryRef",inline:!0},{default:t(()=>[l(i,{label:"部门名称",prop:"deptName"},{default:t(()=>[l(k,{modelValue:n(y).deptName,"onUpdate:modelValue":e[0]||(e[0]=a=>n(y).deptName=a),placeholder:"请输入部门名称",clearable:"",style:{width:"200px"},onKeyup:ve(R,["enter"])},null,8,["modelValue"])]),_:1}),l(i,{label:"状态",prop:"status"},{default:t(()=>[l(ae,{modelValue:n(y).status,"onUpdate:modelValue":e[1]||(e[1]=a=>n(y).status=a),placeholder:"部门状态",clearable:"",style:{width:"200px"}},{default:t(()=>[(p(!0),q(O,null,Q(n(C),a=>(p(),g(te,{key:a.value,label:a.label,value:a.value},null,8,["label","value"]))),128))]),_:1},8,["modelValue"])]),_:1}),l(i,null,{default:t(()=>[l(f,{type:"primary",icon:"Search",onClick:R},{default:t(()=>e[11]||(e[11]=[m("搜索")])),_:1}),l(f,{icon:"Refresh",onClick:W},{default:t(()=>e[12]||(e[12]=[m("重置")])),_:1})]),_:1})]),_:1},8,["model"]),[[_e,n(N)]]),l(L,{gutter:10,class:"mb8"},{default:t(()=>[l(c,{span:1.5},{default:t(()=>[h((p(),g(f,{type:"primary",plain:"",icon:"Plus",onClick:F},{default:t(()=>e[13]||(e[13]=[m("新增")])),_:1})),[[I,["system:dept:add"]]])]),_:1}),l(c,{span:1.5},{default:t(()=>[l(f,{type:"info",plain:"",icon:"Sort",onClick:Y},{default:t(()=>e[14]||(e[14]=[m("展开/折叠")])),_:1})]),_:1}),l(ne,{showSearch:n(N),"onUpdate:showSearch":e[2]||(e[2]=a=>j(N)?N.value=a:null),onQueryTable:b},null,8,["showSearch"])]),_:1}),n(T)?h((p(),g(de,{key:0,data:n(E),"row-key":"deptId","default-expand-all":n(S),"tree-props":{children:"children",hasChildren:"hasChildren"}},{default:t(()=>[l(w,{prop:"deptName",label:"部门名称",width:"260"}),l(w,{prop:"orderNum",label:"排序",width:"200"}),l(w,{prop:"status",label:"状态",width:"100"},{default:t(a=>[l(oe,{options:n(C),value:a.row.status},null,8,["options","value"])]),_:1}),l(w,{label:"创建时间",align:"center",prop:"createTime",width:"200"},{default:t(a=>[H("span",null,J(u.parseTime(a.row.createTime)),1)]),_:1}),l(w,{label:"操作",align:"center","class-name":"small-padding fixed-width"},{default:t(a=>[h((p(),g(f,{link:"",type:"primary",icon:"Edit",onClick:A=>Z(a.row)},{default:t(()=>e[15]||(e[15]=[m("修改")])),_:2},1032,["onClick"])),[[I,["system:dept:edit"]]]),h((p(),g(f,{link:"",type:"primary",icon:"Plus",onClick:A=>F(a.row)},{default:t(()=>e[16]||(e[16]=[m("新增")])),_:2},1032,["onClick"])),[[I,["system:dept:add"]]]),a.row.parentId!=0?h((p(),g(f,{key:0,link:"",type:"primary",icon:"Delete",onClick:A=>le(a.row)},{default:t(()=>e[17]||(e[17]=[m("删除")])),_:2},1032,["onClick"])),[[I,["system:dept:remove"]]]):P("",!0)]),_:1})]),_:1},8,["data","default-expand-all"])),[[me,n(x)]]):P("",!0),l(ie,{title:n(D),modelValue:n(_),"onUpdate:modelValue":e[10]||(e[10]=a=>j(_)?_.value=a:null),width:"600px","append-to-body":""},{footer:t(()=>[H("div",Ce,[l(f,{type:"primary",onClick:ee},{default:t(()=>e[18]||(e[18]=[m("确 定")])),_:1}),l(f,{onClick:G},{default:t(()=>e[19]||(e[19]=[m("取 消")])),_:1})])]),default:t(()=>[l(B,{ref:"deptRef",model:n(o),rules:n(z),"label-width":"80px"},{default:t(()=>[l(L,null,{default:t(()=>[n(o).parentId!==0?(p(),g(c,{key:0,span:24},{default:t(()=>[l(i,{label:"上级部门",prop:"parentId"},{default:t(()=>[l(ue,{modelValue:n(o).parentId,"onUpdate:modelValue":e[3]||(e[3]=a=>n(o).parentId=a),data:n(U),props:{value:"deptId",label:"deptName",children:"children"},"value-key":"deptId",placeholder:"选择上级部门","check-strictly":""},null,8,["modelValue","data"])]),_:1})]),_:1})):P("",!0),l(c,{span:12},{default:t(()=>[l(i,{label:"部门名称",prop:"deptName"},{default:t(()=>[l(k,{modelValue:n(o).deptName,"onUpdate:modelValue":e[4]||(e[4]=a=>n(o).deptName=a),placeholder:"请输入部门名称"},null,8,["modelValue"])]),_:1})]),_:1}),l(c,{span:12},{default:t(()=>[l(i,{label:"显示排序",prop:"orderNum"},{default:t(()=>[l(re,{modelValue:n(o).orderNum,"onUpdate:modelValue":e[5]||(e[5]=a=>n(o).orderNum=a),"controls-position":"right",min:0},null,8,["modelValue"])]),_:1})]),_:1}),l(c,{span:12},{default:t(()=>[l(i,{label:"负责人",prop:"leader"},{default:t(()=>[l(k,{modelValue:n(o).leader,"onUpdate:modelValue":e[6]||(e[6]=a=>n(o).leader=a),placeholder:"请输入负责人",maxlength:"20"},null,8,["modelValue"])]),_:1})]),_:1}),l(c,{span:12},{default:t(()=>[l(i,{label:"联系电话",prop:"phone"},{default:t(()=>[l(k,{modelValue:n(o).phone,"onUpdate:modelValue":e[7]||(e[7]=a=>n(o).phone=a),placeholder:"请输入联系电话",maxlength:"11"},null,8,["modelValue"])]),_:1})]),_:1}),l(c,{span:12},{default:t(()=>[l(i,{label:"邮箱",prop:"email"},{default:t(()=>[l(k,{modelValue:n(o).email,"onUpdate:modelValue":e[8]||(e[8]=a=>n(o).email=a),placeholder:"请输入邮箱",maxlength:"50"},null,8,["modelValue"])]),_:1})]),_:1}),l(c,{span:12},{default:t(()=>[l(i,{label:"部门状态"},{default:t(()=>[l(pe,{modelValue:n(o).status,"onUpdate:modelValue":e[9]||(e[9]=a=>n(o).status=a)},{default:t(()=>[(p(!0),q(O,null,Q(n(C),a=>(p(),g(se,{key:a.value,label:a.value},{default:t(()=>[m(J(a.label),1)]),_:2},1032,["label"]))),128))]),_:1},8,["modelValue"])]),_:1})]),_:1})]),_:1})]),_:1},8,["model","rules"])]),_:1},8,["title","modelValue"])])}}});export{Ue as default};