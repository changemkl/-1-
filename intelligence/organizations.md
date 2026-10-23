# 客户组织树

`public/organization-data.json` 独立保存组织资料，以腾讯表格的客户编号关联。表格只负责客户名称，不覆盖机构名单；采购采集和 profile-data 发布也不会覆盖此文件。

每条记录包含 `id`、`nodes`（递归的 name/children）、`note`，有机构资料时必须包含 `checkedAt` 和 `source`（或 `sources`）。来源记录保存官方 URL、标题和发布日期。只录入原文明确载明的机构及隶属关系；不把行业协会、兄弟单位或业务合作方推断为下属机构。部分名单必须在节点标题或 note 中注明。旧页面只能表示该页面公开的名单，不能据此声称是现行完整架构。

页面点击卡片的“组织架构”按钮后打开右侧面板。更新 JSON 并发布即可更新资料，机构节点可展开或收起。没有已核实资料的客户显示待补充，不生成通用部门。当前未接入组织资料自动采集。

验证：`node --test tests/organizations.test.cjs`、`npm run check`。
