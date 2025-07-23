# 本地提示词管理软件 - 任务列表

## Relevant Files

- `main.py` - 主程序入口和应用程序启动逻辑
- `pyproject.toml` - uv项目配置文件，定义项目元数据和依赖
- `requirements.txt` - Python依赖包清单，包含所有必需的第三方库
- `.venv/` - uv创建的Python虚拟环境，包含所有已安装的依赖
- `modules/__init__.py` - 模块包初始化文件，提供便捷的导入接口
- `modules/config_manager.py` - 配置文件管理模块，处理全局配置和快捷键映射
- `modules/project_initializer.py` - 项目初始化模块，负责自动创建目录结构和示例文件
- `modules/template_parser.py` - 提示词模板解析模块，实现.md文件读取和内容解析功能
- `modules/model_client.py` - AI模型客户端，实现Deepseek和Kimi API调用
- `modules/hotkey_listener.py` - 全局快捷键监听器模块，负责监听和处理系统级快捷键事件
- `modules/text_processor.py` - 文本处理模块，处理选中文本获取和流式输出
- `config/global_config.yaml` - 全局配置文件，存储API密钥和模型配置（带详细注释）
- `config/global_config.example.yaml` - 全局配置示例文件，展示正确的配置格式
- `config/hotkey_mapping.yaml` - 快捷键映射配置文件，定义快捷键与模板的映射关系
- `config/hotkey_mapping.example.yaml` - 快捷键配置示例文件，展示实际使用场景
- `prompt/` - 提示词模板存储目录（程序启动时自动创建）
- `prompt/README.md` - 提示词模板使用说明文档
- `prompt/translate.md` - 翻译助手示例模板
- `prompt/summarize.md` - 文本摘要示例模板
- `prompt/grammar_check.md` - 语法检查示例模板
- `tests/test_config_manager.py` - 配置管理模块测试
- `tests/test_config_reload_demo.py` - 配置文件动态重新加载功能演示脚本
- `tests/test_hotkey_listener.py` - 快捷键监听器模块测试，验证control+option+command+1-9功能
- `tests/test_dynamic_mapping.py` - 动态映射功能测试，验证模板文件的动态发现和映射机制
- `tests/test_template_parser.py` - 模板解析模块测试
- `tests/test_model_client.py` - 模型客户端测试
- `tests/test_hotkey_listener.py` - 快捷键监听器测试
- `tests/test_text_processor.py` - 文本处理模块测试

### Notes

- 使用 `pytest` 作为测试框架
- 配置文件使用YAML格式便于人工编辑
- 模块化设计便于单独测试和维护
- 支持异步操作以提高响应性能

## Tasks

- [x] 1.0 项目基础架构和配置系统
  - [x] 1.1 创建项目目录结构（modules/, config/, prompt/, tests/）
  - [x] 1.2 初始化requirements.txt，包含pynput、pyperclip、requests、PyYAML等依赖
  - [x] 1.3 创建config_manager.py模块，实现配置文件的读取、写入和验证功能
  - [x] 1.4 设计并创建global_config.yaml模板，包含Deepseek和Kimi的API密钥配置
  - [x] 1.5 设计并创建hotkey_mapping.yaml模板，支持1-9快捷键到模板文件的映射
  - [x] 1.6 实现配置文件的动态重新加载功能
  - [x] 1.7 程序启动时自动创建prompt文件夹的逻辑

- [x] 2.0 提示词模板解析系统
  - [x] 2.1 创建template_parser.py模块，实现.md文件的基本读取功能
  - [x] 2.2 实现使用"---"分隔符解析模型信息和提示词内容
  - [x] 2.3 实现{{变量名}}占位符的识别和替换功能
  - [x] 2.4 添加模板验证逻辑（确保每个模板只有一个占位符）
  - [x] 2.5 实现prompt文件夹的自动扫描和.md文件加载
  - [x] 2.6 创建模板缓存机制，提高重复调用的性能
  - [x] 2.7 添加模板文件变化的监控和自动重新加载

- [x] 3.0 AI模型客户端集成
  - [x] 3.1 创建model_client.py模块，设计统一的模型调用接口
  - [x] 3.2 实现Deepseek API客户端，支持完整的请求和响应处理
  - [x] 3.3 实现Kimi API客户端，支持完整的请求和响应处理
  - [x] 3.4 实现流式响应处理，支持实时数据流解析
  - [x] 3.5 添加API调用的错误处理和重试机制
  - [x] 3.6 实现模型响应的异步处理，避免阻塞主线程
  - [x] 3.7 添加API调用的超时控制和连接管理

- [ ] 4.0 全局快捷键监听系统
  - [x] 4.1 创建hotkey_listener.py模块，初始化全局快捷键监听器
  - [x] 4.2 实现control+option+command+1-9快捷键的注册和监听
  - [x] 4.3 实现快捷键到模板文件的动态映射机制
  - [x] 4.4 添加快捷键冲突检测和错误处理
  - [x] 4.5 实现后台监听状态的维护和管理
  - [x] 4.6 添加快捷键配置的热重载功能
  - [x] 4.7 实现跨平台兼容性处理（主要针对macOS）

- [ ] 5.0 文本处理和流式输出系统
  - [ ] 5.1 创建text_processor.py模块，实现当前选中文本的获取功能
  - [ ] 5.2 实现选中文本到模板占位符的自动插入逻辑
  - [ ] 5.3 实现模型响应的实时流式输出到光标位置（文本末尾）
  - [ ] 5.4 添加文本为空时的错误处理（输出"!!文本为空!!"）
  - [ ] 5.5 添加API不可用时的错误处理（输出"!!api不可用!!"）
  - [ ] 5.6 实现剪贴板操作的备用输出机制
  - [ ] 5.7 添加文本输出的字符编码处理和特殊字符过滤

- [ ] 6.0 主程序集成和测试
  - [ ] 6.1 创建main.py主程序，整合所有模块功能
  - [ ] 6.2 实现程序的优雅启动和关闭机制
  - [ ] 6.3 添加基本的日志记录功能
  - [ ] 6.4 创建完整的单元测试覆盖所有核心模块
  - [ ] 6.5 进行端到端功能测试和性能测试
  - [ ] 6.6 编写用户使用说明和配置示例
  - [ ] 6.7 优化程序性能，确保快捷键响应时间<500ms 