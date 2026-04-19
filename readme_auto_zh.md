# API 测试平台

## 简介
API 测试平台是一个用于测试和验证 RESTful API 的工具。它允许用户执行各种请求，如 GET、POST、PUT 和 DELETE，以确保 API 的功能和性能符合预期。

## 功能
- **请求构建**: 用户可以轻松构建请求，包括请求头、参数和正文。
- **结果验证**: 可以检查返回的状态码和响应时间，确保 API 的响应符合预期。
- **数据驱动测试**: 支持通过外部数据源驱动测试，用于批量测试各种请求和参数组合。
- **报告生成**: 自动生成测试报告，提供详细的测试结果和日志。

## 安装
1. 克隆该项目:
   ```bash
   git clone https://github.com/diaodeng/ApiTestPlatform.git
   ```
2. 安装依赖:
   ```bash
   cd ApiTestPlatform
   npm install
   ```

## 使用
1. 启动平台:
   ```bash
   npm start
   ```
2. 打开浏览器，访问 `http://localhost:3000`
3. 根据需要创建和管理 API 测试。

## 贡献
欢迎任何贡献！请提交问题和拉取请求。

## 许可证
该项目采用 MIT 许可证，详见 LICENSE 文件。