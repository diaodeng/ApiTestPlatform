import{au as he,A as He,v as ue,d,o as i,m,f as n,e as t,h as e,p as y,y as S,c as P,O as G,P as X,az as Fe,r as s,a6 as oe,a5 as Ke,C as Le,H as we,I as g,M as Ce,l as Ie,K as V,n as Q,i as J,F as Ae,s as Qe,av as W,E as Je,aA as We,ab as Ge}from"./index.B-ki0wTK.js";import{c as Xe,a as Ye,l as Ze,b as el,e as ll}from"./case.D3mpduVc.js";import{s as al}from"./module.DGh92-sK.js";import{H as T,r as tl,R as nl,l as ol}from"./project.CjUq6QCv.js";import{d as sl,_ as ul}from"./run-detail.D4F0Zf9c.js";import{i as se}from"./data-template.D-VuWITS.js";import{_ as dl}from"./run_dialog.hwjk6Wms.js";import"./run_detail.B7CDhMn4.js";import"./env.BXDgmL9O.js";import"./table-variables.9YKN3mfF.js";import"./tools.CngWgkPu.js";import"./ace-editor.DNfnIcx7.js";import"./ResizeObserver.es.B1PUzC5B.js";const il={__name:"tag-selector",props:he({options:{type:Object},disable:{type:Boolean,default:!1},selectorWidth:{default:"200px"},sourceData:{type:Object}},{selectedValue:{},selectedValueModifiers:{}}),emits:he(["selectChanged"],["update:selectedValue"]),setup(c,{emit:h}){const j=He(c,"selectedValue"),Y=c,U=ue(()=>{const w=Y.options.filter(r=>r.value*1===j.value);return w&&w.length>0?w[0].elTagType:"primary"});return(w,r)=>{const z=d("el-tag"),B=d("el-option"),H=d("el-select");return i(),m(H,{placeholder:"请选择",modelValue:j.value,"onUpdate:modelValue":r[0]||(r[0]=p=>j.value=p),style:Fe({width:c.selectorWidth}),disabled:c.disable,filterable:"",onChange:r[1]||(r[1]=p=>w.$emit("selectChanged",p,c.sourceData))},{label:n(({label:p,value:k})=>[t(z,{round:"",size:"small",type:e(U)},{default:n(()=>[y(S(p),1)]),_:2},1032,["type"])]),loading:n(()=>r[2]||(r[2]=[y("加载中。。。")])),default:n(()=>[(i(!0),P(G,null,X(c.options,p=>(i(),m(B,{key:p.value*1,label:p.label,value:p.value*1},{default:n(()=>[t(z,{round:"",size:"small",type:p.elTagType},{default:n(()=>[y(S(p.label),1)]),_:2},1032,["type"])]),_:2},1032,["label","value"]))),128))]),_:1},8,["modelValue","style","disabled"])}}},rl={class:"app-container"},cl=Ae({name:"Case"}),kl=Object.assign(cl,{props:{dataType:{type:Number,default:T.case},formRules:{type:Object,default:{caseName:[{required:!0,message:"用例名称不能为空",trigger:"blur"}],projectId:[{required:!0,message:"所属项目不能为空",trigger:"blur"}],moduleId:[{required:!0,message:"所属模块不能为空",trigger:"blur"}]}}},setup(c){s(!1),s("久啊联发科打了飞机啊漏打卡飞机啦电极法立卡登记说法法兰对接法拉克束带结发法拉第会计法垃圾");const{proxy:h}=Qe(),{sys_normal_disable:j}=h.useDict("sys_normal_disable");h.useDict("sys_request_method");const{hrm_data_type:Y}=h.useDict("hrm_data_type"),{qtr_case_status:U}=h.useDict("qtr_case_status"),w=c,r=ue(()=>w.dataType===T.case?"用例":"配置"),z=ue(()=>le.value+"【"+E.value.caseId+" - "+E.value.caseName+"】");oe("hrm_data_type",Y),oe("sys_normal_disable",j),oe("qtr_case_status",U);const B=s([]),H=s([]),p=s([]),k=s(!1),F=s(!0),R=s([]),de=s(!0),Z=s(!0),ee=s(0),le=s(""),K=s(!0),L=s(!1),$=s([]),A=s(!1),ae=s(null),ie=s(),x=s(!1),N=s(se),u=Ke({pageNum:1,pageSize:10,type:w.dataType,caseId:void 0,caseName:void 0,projectId:void 0,moduleId:void 0,status:void 0,onlySelf:K}),E=s(se),v=s({page:!1,edite:!1,run:!1,copy:!1});function re(o){return o||"全局"}function Ve(o,l){Xe({caseId:l.caseId,status:o}).then(C=>{W.success("修改成功")}).catch(()=>{W.error("修改失败")})}function ce(o){if(o&&"caseId"in o&&o.caseId&&($.value=[o.caseId]),!$.value||$.value.length===0){Je.alert("请选择要运行的用例","提示！",{type:"warning"});return}L.value=!0}function ke(o){x.value=!0,console.log(V(o)),N.value=structuredClone(We(Ge(o)))}function xe(){x.value=!0;let o={caseId:N.value.caseId,caseName:N.value.caseName};Ye(o).then(l=>{W.success("复制成功")}).finally(()=>{x.value=!1})}function O(){v.value.page=!0,Ze(u.value).then(o=>{B.value=o.rows,ee.value=o.total}).finally(()=>{v.value.page=!1})}function Ne(){ol({isPage:!1}).then(o=>{H.value=o.data})}function De(){al(u.value).then(o=>{p.value=o.data})}function Te(){u.value.moduleId=void 0,De()}function q(){u.value.pageNum=1,O()}function Se(){h.resetForm("queryRef"),q()}function je(o){R.value=o.map(l=>l.caseId),$.value=R.value,de.value=o.length!==1,Z.value=!o.length}function Ue(){le.value="添加"+r.value,E.value=JSON.parse(JSON.stringify(se)),k.value=!0}function pe(o){v.value.edite=!0;const l=o.caseId||R.value;el(l).then(C=>{if(!C.data||Object.keys(C.data).length===0){W.warning("未查到对应数据！");return}E.value=C.data,le.value="修改"+r.value,k.value=!0}).finally(()=>{v.value.edite=!1})}function Re(o){const l=o.caseId||R.value;ae.value=o,ie.value=l,A.value=!0}function me(o){const l=o.caseId||R.value;h.$modal.confirm('是否确认删除ID为"'+l+'"的数据项？').then(function(){return ll(l)}).then(()=>{O(),h.$modal.msgSuccess("删除成功")}).catch(()=>{})}function $e(){h.download("hrm/case/export",{...u.value},`Case_${new Date().getTime()}.xlsx`)}return Le(()=>{Ne(),O()}),(o,l)=>{var ve,be,_e;const C=d("el-option"),te=d("el-select"),I=d("el-form-item"),ne=d("el-input"),Ee=d("el-checkbox"),f=d("el-button"),Oe=d("el-form"),M=d("el-col"),qe=d("right-toolbar"),Me=d("el-row"),b=d("el-table-column"),Pe=d("el-table"),ze=d("pagination"),fe=d("el-main"),ge=d("el-container"),ye=d("el-dialog"),_=we("hasPermi"),Be=we("loading");return i(),P("div",rl,[g(t(Oe,{model:e(u),ref:"queryRef",inline:!0},{default:n(()=>[t(I,{label:"所属项目",prop:"projectId"},{default:n(()=>[t(te,{modelValue:e(u).projectId,"onUpdate:modelValue":l[0]||(l[0]=a=>e(u).projectId=a),placeholder:"请选择",onChange:Te,clearable:"",filterable:"",style:{width:"150px"}},{default:n(()=>[(i(!0),P(G,null,X(e(H),a=>(i(),m(C,{key:a.projectId,label:a.projectName,value:a.projectId},null,8,["label","value"]))),128))]),_:1},8,["modelValue"])]),_:1}),t(I,{label:"所属模块",prop:"moduleId"},{default:n(()=>[t(te,{modelValue:e(u).moduleId,"onUpdate:modelValue":l[1]||(l[1]=a=>e(u).moduleId=a),placeholder:"请选择",clearable:"",filterable:"",style:{width:"150px"}},{default:n(()=>[(i(!0),P(G,null,X(e(p),a=>(i(),m(C,{key:a.moduleId,label:a.moduleName,value:a.moduleId},null,8,["label","value"]))),128))]),_:1},8,["modelValue"])]),_:1}),t(I,{label:e(r)+"ID",prop:"caseId"},{default:n(()=>[t(ne,{modelValue:e(u).caseId,"onUpdate:modelValue":l[2]||(l[2]=a=>e(u).caseId=a),placeholder:"请输入"+e(r)+"名称",clearable:"",style:{width:"200px"},onKeyup:Ie(q,["enter"])},null,8,["modelValue","placeholder"])]),_:1},8,["label"]),t(I,{label:e(r)+"名称",prop:"caseName"},{default:n(()=>[t(ne,{modelValue:e(u).caseName,"onUpdate:modelValue":l[3]||(l[3]=a=>e(u).caseName=a),placeholder:"请输入"+e(r)+"名称",clearable:"",style:{width:"200px"},onKeyup:Ie(q,["enter"])},null,8,["modelValue","placeholder"])]),_:1},8,["label"]),t(I,{label:"状态",prop:"status"},{default:n(()=>[t(te,{modelValue:e(u).status,"onUpdate:modelValue":l[4]||(l[4]=a=>e(u).status=a),placeholder:e(r)+"状态",clearable:"",style:{width:"100px"}},{default:n(()=>[(i(!0),P(G,null,X(e(U),a=>(i(),m(C,{key:a.value,label:a.label,value:a.value},null,8,["label","value"]))),128))]),_:1},8,["modelValue","placeholder"])]),_:1}),t(I,null,{default:n(()=>[t(Ee,{modelValue:e(K),"onUpdate:modelValue":l[5]||(l[5]=a=>V(K)?K.value=a:null),onChange:q},{default:n(()=>l[14]||(l[14]=[y("仅自己的数据")])),_:1},8,["modelValue"])]),_:1}),t(I,null,{default:n(()=>[t(f,{type:"primary",icon:"Search",onClick:q,loading:e(v).page,disabled:e(v).page},{default:n(()=>l[15]||(l[15]=[y(" 搜索 ")])),_:1},8,["loading","disabled"]),t(f,{type:"default",icon:"Refresh",onClick:Se},{default:n(()=>l[16]||(l[16]=[y("重置")])),_:1})]),_:1})]),_:1},8,["model"]),[[Ce,e(F)]]),t(Me,{gutter:10,class:"mb8"},{default:n(()=>[t(M,{span:1.5},{default:n(()=>[g((i(),m(f,{type:"primary",plain:"",icon:"Plus",onClick:Ue},{default:n(()=>l[17]||(l[17]=[y("新增 ")])),_:1})),[[_,["hrm:case:add"]]])]),_:1}),t(M,{span:1.5},{default:n(()=>[g((i(),m(f,{type:"success",plain:"",icon:"Edit",disabled:e(de),onClick:pe},{default:n(()=>l[18]||(l[18]=[y("修改 ")])),_:1},8,["disabled"])),[[_,["hrm:case:edit"]]])]),_:1}),t(M,{span:1.5},{default:n(()=>[g((i(),m(f,{type:"danger",plain:"",icon:"Delete",disabled:e(Z),onClick:me},{default:n(()=>l[19]||(l[19]=[y("删除 ")])),_:1},8,["disabled"])),[[_,["hrm:case:remove"]]])]),_:1}),t(M,{span:1.5},{default:n(()=>[g((i(),m(f,{type:"warning",plain:"",icon:"Download",onClick:$e},{default:n(()=>l[20]||(l[20]=[y("导出 ")])),_:1})),[[_,["hrm:case:export"]]])]),_:1}),t(M,{span:1.5},{default:n(()=>[c.dataType===e(T).case?g((i(),m(f,{key:0,type:"warning",icon:"CaretRight",onClick:ce,title:"运行",disabled:e(Z)},{default:n(()=>l[21]||(l[21]=[y(" 执行 ")])),_:1},8,["disabled"])),[[_,["hrm:case:run"]]]):Q("",!0)]),_:1}),t(qe,{showSearch:e(F),"onUpdate:showSearch":l[6]||(l[6]=a=>V(F)?F.value=a:null),onQueryTable:O},null,8,["showSearch"])]),_:1}),g((i(),m(Pe,{data:e(B),onSelectionChange:je,border:"","table-layout":"fixed","max-height":"calc(100vh - 280px)"},{default:n(()=>[t(b,{type:"selection",width:"55",align:"center"}),t(b,{label:e(r)+"ID",prop:"caseId",width:"150px"},null,8,["label"]),t(b,{label:e(r)+"名称",prop:"caseName",width:"auto","min-width":"200px"},null,8,["label"]),t(b,{label:"所属项目",prop:"projectName"},{default:n(a=>[J("span",null,S(re(a.row.projectName)),1)]),_:1}),t(b,{label:"所属模块",prop:"moduleName"},{default:n(a=>[J("span",null,S(re(a.row.moduleName)),1)]),_:1}),t(b,{label:"状态",align:"center",prop:"status",width:"120px"},{default:n(a=>[t(il,{"selected-value":a.row.status,"onUpdate:selectedValue":D=>a.row.status=D,options:e(U),"selector-width":"90px","source-data":a.row,onSelectChanged:Ve},null,8,["selected-value","onUpdate:selectedValue","options","source-data"])]),_:1}),t(b,{label:"创建人",align:"center",prop:"createBy",width:"80px"}),t(b,{label:"创建时间",align:"center",prop:"createTime","class-name":"small-padding fixed-width",width:"150px"},{default:n(a=>[J("span",null,S(o.parseTime(a.row.createTime)),1)]),_:1}),t(b,{label:"更新时间",align:"center",prop:"createTime","class-name":"small-padding fixed-width",width:"150px"},{default:n(a=>[J("span",null,S(o.parseTime(a.row.updateTime)),1)]),_:1}),t(b,{label:"操作",width:"170",align:"center","class-name":"small-padding fixed-width",fixed:"right"},{default:n(a=>[c.dataType===e(T).case?g((i(),m(f,{key:0,link:"",type:"primary",icon:"Histogram",onClick:D=>Re(a.row),title:"执行历史"},null,8,["onClick"])),[[_,["hrm:case:history"]]]):Q("",!0),g(t(f,{link:"",type:"warning",icon:"Edit",loading:e(v).edite,onClick:D=>pe(a.row),title:"编辑"},null,8,["loading","onClick"]),[[_,["hrm:case:edit"]]]),c.dataType===e(T).case?g((i(),m(f,{key:1,link:"",type:"warning",icon:"CaretRight",loading:e(v).run,onClick:D=>ce(a.row),title:"运行"},null,8,["loading","onClick"])),[[_,["hrm:case:run"]]]):Q("",!0),g(t(f,{link:"",type:"warning",icon:"CopyDocument",loading:e(v).copy,onClick:D=>ke(a.row),title:"复制"},null,8,["loading","onClick"]),[[_,["hrm:case:copy"]]]),g(t(f,{link:"",type:"danger",icon:"Delete",onClick:D=>me(a.row),title:"删除"},null,8,["onClick"]),[[_,["hrm:case:remove"]]])]),_:1})]),_:1},8,["data"])),[[Be,e(v).page]]),g(t(ze,{total:e(ee),page:e(u).pageNum,"onUpdate:page":l[7]||(l[7]=a=>e(u).pageNum=a),limit:e(u).pageSize,"onUpdate:limit":l[8]||(l[8]=a=>e(u).pageSize=a),onPagination:O},null,8,["total","page","limit"]),[[Ce,e(ee)>0]]),t(sl,{"form-datas":e(E),"data-type":c.dataType,"form-rules":c.formRules,"open-case-edit-dialog":e(k),"onUpdate:openCaseEditDialog":l[9]||(l[9]=a=>V(k)?k.value=a:null),title:e(z)},null,8,["form-datas","data-type","form-rules","open-case-edit-dialog","title"]),c.dataType===e(T).case?(i(),m(ye,{key:0,fullscreen:"",title:"【"+((ve=e(ae))==null?void 0:ve.caseId)+"】"+((be=e(ae))==null?void 0:be.caseName),modelValue:e(A),"onUpdate:modelValue":l[10]||(l[10]=a=>V(A)?A.value=a:null),"append-to-body":"","destroy-on-close":""},{default:n(()=>[t(ge,{style:{height:"100%"}},{default:n(()=>[t(fe,{style:{"max-height":"calc(100vh - 95px)"}},{default:n(()=>[t(ul,{"run-id":e(ie),"view-type":e(tl).case},null,8,["run-id","view-type"])]),_:1})]),_:1})]),_:1},8,["title","modelValue"])):Q("",!0),t(ye,{title:(_e=e(N))==null?void 0:_e.caseName,modelValue:e(x),"onUpdate:modelValue":l[12]||(l[12]=a=>V(x)?x.value=a:null),"append-to-body":"","destroy-on-close":""},{default:n(()=>[t(ge,{style:{height:"100%"}},{default:n(()=>[t(fe,{style:{"max-height":"calc(100vh - 95px)"}},{default:n(()=>[t(ne,{placeholder:"请输入用例名称",modelValue:e(N).caseName,"onUpdate:modelValue":l[11]||(l[11]=a=>e(N).caseName=a)},{suffix:n(()=>[t(f,{onClick:xe},{default:n(()=>l[22]||(l[22]=[y("保存")])),_:1})]),_:1},8,["modelValue"])]),_:1})]),_:1})]),_:1},8,["title","modelValue"]),t(dl,{"dialog-visible":e(L),"onUpdate:dialogVisible":l[13]||(l[13]=a=>V(L)?L.value=a:null),"run-type":e(nl).case,"run-ids":e($)},null,8,["dialog-visible","run-type","run-ids"])])}}});export{kl as default};