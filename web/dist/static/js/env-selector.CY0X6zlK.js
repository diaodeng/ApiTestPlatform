import{X as m,av as z,A as C,r as V,C as h,d as y,o as s,m as a,f as n,c as d,O as i,P as E,h as b,p as r,n as u,y as k,aC as B}from"./index.DgyczuKs.js";import{b as L}from"./env.D40RgY2q.js";function T(t){return m({url:"/hrm/runner/runHistoryList",method:"get",params:t})}function H(t){return m({url:"/hrm/runner/runHistory",method:"DELETE",data:t})}function I(t){return m({url:`/hrm/runner/runHistory/${t}`,method:"GET"})}function O(t){return m({url:"/hrm/runner/test",method:"POST",data:t})}const w={__name:"env-selector",props:z({disable:{type:Boolean,default:!1},selectorWidth:{default:"200px"}},{selectedEnv:{},selectedEnvModifiers:{}}),emits:["update:selectedEnv"],setup(t){const c=C(t,"selectedEnv"),f=V([]);function g(){L().then(p=>{f.value=p.data})}return h(()=>{g()}),(p,e)=>{const o=y("el-tag"),S=y("el-option"),_=y("el-select");return s(),a(_,{placeholder:"选择环境",modelValue:c.value,"onUpdate:modelValue":e[0]||(e[0]=l=>c.value=l),style:B({width:t.selectorWidth}),disabled:t.disable,filterable:""},{label:n(({label:l,value:x})=>[(s(!0),d(i,null,E(b(f),v=>(s(),d(i,null,[v.envId===x?(s(),d(i,{key:0},[v.isSelf?(s(),a(o,{key:0,round:"",size:"small",type:"success"},{default:n(()=>e[1]||(e[1]=[r("可管理")])),_:1})):u("",!0),v.isSelf?u("",!0):(s(),a(o,{key:1,round:"",size:"small",type:"info"},{default:n(()=>e[2]||(e[2]=[r("可使用")])),_:1}))],64)):u("",!0)],64))),256)),r(" "+k(l),1)]),loading:n(()=>e[3]||(e[3]=[r("加载中。。。")])),default:n(()=>[(s(!0),d(i,null,E(b(f),l=>(s(),a(S,{key:l.envId,label:l.envName,value:l.envId},{default:n(()=>[l.isSelf?(s(),a(o,{key:0,round:"",size:"small",type:"success"},{default:n(()=>e[4]||(e[4]=[r("可管理")])),_:1})):u("",!0),l.isSelf?u("",!0):(s(),a(o,{key:1,round:"",size:"small",type:"info"},{default:n(()=>e[5]||(e[5]=[r("可使用")])),_:1})),r(" "+k(l.envName),1)]),_:2},1032,["label","value"]))),128))]),_:1},8,["modelValue","style","disabled"])}}};export{w as _,I as a,H as d,T as l,O as t};