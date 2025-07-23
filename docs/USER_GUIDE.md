# 本地提示词管理软件 - 用户使用指南

## 📋 目录

- [概述](#概述)
- [系统要求](#系统要求)
- [安装指南](#安装指南)
- [配置说明](#配置说明)
- [使用方法](#使用方法)
- [模板管理](#模板管理)
- [快捷键配置](#快捷键配置)
- [故障排除](#故障排除)
- [性能优化](#性能优化)
- [常见问题](#常见问题)

## 📖 概述

本地提示词管理软件是一个通过全局快捷键触发的AI助手工具。它可以：

- 🔤 自动获取当前选中的文本
- 📝 将文本插入预设的提示词模板
- 🤖 调用AI模型处理内容
- ⌨️ 将结果实时流式输出到光标位置

### 核心功能

- **全局快捷键**：`Ctrl+Alt+Cmd+1-9` 触发不同模板
- **文本选择**：自动获取当前选中文本
- **模板系统**：支持YAML前置配置和Markdown模板
- **AI集成**：支持Deepseek和Kimi模型
- **流式输出**：实时打字效果输出
- **智能过滤**：自动处理特殊字符和编码问题

## 💻 系统要求

### 支持平台
- macOS 10.15+ (推荐)
- Windows 10+
- Linux (Ubuntu 18.04+)

### 软件依赖
- Python 3.8+
- 网络连接（调用AI API）

### 权限要求（macOS）
- **辅助功能权限**：监听全局快捷键
- **输入监控权限**：获取选中文本
- **屏幕录制权限**：某些情况下需要

## 🚀 安装指南

### 方法一：使用uv（推荐）

```bash
# 1. 安装uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 克隆项目
git clone <repository-url> prompt_go
cd prompt_go

# 3. 安装依赖
uv sync

# 4. 运行程序
uv run python main.py
```

### 方法二：使用pip

```bash
# 1. 克隆项目
git clone <repository-url> prompt_go
cd prompt_go

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行程序
python main.py
```

## ⚙️ 配置说明

### 1. 全局配置文件

创建 `config/global_config.yaml`：

```yaml
# API配置
api:
  deepseek:
    base_url: https://api.deepseek.com
    key: 'sk-your-deepseek-api-key'
    model: deepseek-chat
  
  kimi:
    base_url: https://api.moonshot.cn
    key: 'sk-your-kimi-api-key'
    model: moonshot-v1-8k

# 日志配置
logging:
  level: INFO
  file: prompt_manager.log
  max_size: 10485760  # 10MB
  backup_count: 5
  auto_cleanup: true
  cleanup_days: 30

# 性能配置
performance:
  typing_speed: 0.01      # 打字速度（秒/字符）
  timeout: 30             # API超时时间
  max_tokens: 2000        # 最大生成tokens
  chunk_output_delay: 0.05 # 流式输出延迟
```

### 2. 快捷键配置文件

创建 `config/hotkey_mapping.yaml`：

```yaml
# 快捷键映射配置
hotkey_mappings:
  # 基础快捷键：Ctrl+Alt+Cmd+数字
  'ctrl+alt+cmd+1': 'summarize.md'     # 总结
  'ctrl+alt+cmd+2': 'translate.md'     # 翻译
  'ctrl+alt+cmd+3': 'grammar_check.md' # 语法检查
  'ctrl+alt+cmd+4': 'explain.md'       # 解释说明
  'ctrl+alt+cmd+5': 'improve.md'       # 改进建议
  'ctrl+alt+cmd+6': 'analyze.md'       # 分析
  'ctrl+alt+cmd+7': 'extract.md'       # 提取要点
  'ctrl+alt+cmd+8': 'rewrite.md'       # 重写
  'ctrl+alt+cmd+9': 'custom.md'        # 自定义

# 配置选项
settings:
  enable_notifications: true    # 启用通知
  auto_reload: true            # 自动重载配置
  debounce_time: 0.5          # 防抖时间
  
# 冲突解决
conflict_resolution:
  strategy: 'auto'  # auto, manual, ignore
  backup_on_change: true
```

## 📚 使用方法

### 基本使用流程

1. **启动程序**
   ```bash
   uv run python main.py
   ```

2. **选择文本**
   - 在任意应用中选中要处理的文本

3. **触发快捷键**
   - 按下 `Ctrl+Alt+Cmd+1` 到 `Ctrl+Alt+Cmd+9`

4. **查看结果**
   - AI处理结果将自动输出到当前光标位置

### 命令行选项

```bash
# 基本运行
python main.py

# 指定配置目录
python main.py --config custom_config

# 指定模板目录
python main.py --prompt custom_templates

# 启用调试模式
python main.py --debug

# 查看版本
python main.py --version

# 查看帮助
python main.py --help
```

### 日志查看

```bash
# 查看实时日志
tail -f prompt_manager.log

# 查看错误日志
tail -f error_prompt_manager.log

# 查看最近100行
tail -n 100 prompt_manager.log
```

## 📝 模板管理

### 模板文件结构

模板文件位于 `prompt/` 目录，使用Markdown格式：

```markdown
---
model: deepseek-chat
temperature: 0.7
max_tokens: 1000
stream: true
---

请总结以下文本的主要内容：

{{text}}

要求：
- 保持客观中性
- 突出重点信息
- 控制在200字以内
```

### 模板语法

1. **YAML前置配置**（可选）
   ```yaml
   ---
   model: deepseek-chat     # 使用的模型
   temperature: 0.7         # 创造性参数
   max_tokens: 1000         # 最大输出长度
   stream: true             # 是否流式输出
   timeout: 30              # 超时时间
   ---
   ```

2. **占位符**
   - `{{text}}` - 自动插入选中的文本
   - `{{clipboard}}` - 剪贴板内容
   - `{{datetime}}` - 当前时间
   - `{{user}}` - 用户名

3. **条件语法**（高级）
   ```markdown
   {% if text|length > 100 %}
   这是一段较长的文本，需要详细分析：
   {% else %}
   这是一段简短的文本：
   {% endif %}
   
   {{text}}
   ```

### 内置模板示例

#### 1. 总结模板 (`summarize.md`)
```markdown
---
model: deepseek-chat
temperature: 0.3
max_tokens: 500
---

请对以下内容进行简洁的总结：

{{text}}

总结要求：
- 保留核心信息
- 逻辑清晰
- 控制在150字以内
```

#### 2. 翻译模板 (`translate.md`)
```markdown
---
model: deepseek-chat
temperature: 0.2
max_tokens: 1000
---

请将以下文本翻译成英文，保持原意和语调：

{{text}}

翻译要求：
- 准确传达原意
- 语言自然流畅
- 保持专业术语的准确性
```

#### 3. 语法检查模板 (`grammar_check.md`)
```markdown
---
model: deepseek-chat
temperature: 0.1
max_tokens: 800
---

请检查以下文本的语法错误并提供修正建议：

{{text}}

检查要点：
- 语法错误
- 标点符号
- 用词准确性
- 句式优化建议
```

## ⌨️ 快捷键配置

### 默认快捷键映射

| 快捷键 | 功能 | 模板文件 |
|--------|------|----------|
| `Ctrl+Alt+Cmd+1` | 文本总结 | `summarize.md` |
| `Ctrl+Alt+Cmd+2` | 中英翻译 | `translate.md` |
| `Ctrl+Alt+Cmd+3` | 语法检查 | `grammar_check.md` |
| `Ctrl+Alt+Cmd+4` | 内容解释 | `explain.md` |
| `Ctrl+Alt+Cmd+5` | 改进建议 | `improve.md` |
| `Ctrl+Alt+Cmd+6` | 内容分析 | `analyze.md` |
| `Ctrl+Alt+Cmd+7` | 要点提取 | `extract.md` |
| `Ctrl+Alt+Cmd+8` | 内容重写 | `rewrite.md` |
| `Ctrl+Alt+Cmd+9` | 自定义处理 | `custom.md` |

### 自定义快捷键

编辑 `config/hotkey_mapping.yaml`：

```yaml
hotkey_mappings:
  # 自定义快捷键组合
  'ctrl+alt+cmd+q': 'quick_note.md'
  'ctrl+alt+cmd+w': 'writing_assist.md'
  'ctrl+alt+cmd+e': 'email_polish.md'
  
  # 支持的修饰键组合
  'ctrl+shift+alt+1': 'advanced_analysis.md'
  'cmd+option+1': 'mac_specific.md'
```

### 快捷键冲突处理

程序会自动检测快捷键冲突并提供解决方案：

1. **自动解决**：程序建议替代快捷键
2. **手动解决**：用户选择保留哪个快捷键
3. **忽略冲突**：继续使用可能冲突的快捷键

## 🔧 故障排除

### 常见问题及解决方案

#### 1. 快捷键不响应

**可能原因**：
- 权限不足
- 快捷键冲突
- 程序未正常启动

**解决方案**：
```bash
# 检查程序状态
ps aux | grep python

# 重新启动程序
python main.py --debug

# 检查权限（macOS）
# 系统偏好设置 > 安全性与隐私 > 辅助功能
```

#### 2. 无法获取选中文本

**可能原因**：
- 剪贴板权限问题
- 文本选择方式不当
- 应用程序安全限制

**解决方案**：
```bash
# 测试剪贴板功能
python -c "import pyperclip; print(pyperclip.paste())"

# 检查快捷键模拟
python -c "from pynput.keyboard import Controller; Controller().type('test')"
```

#### 3. API调用失败

**可能原因**：
- API密钥错误
- 网络连接问题
- API服务不可用

**解决方案**：
```bash
# 测试API连接
curl -H "Authorization: Bearer sk-your-key" \
     -H "Content-Type: application/json" \
     "https://api.deepseek.com/v1/models"

# 检查配置文件
cat config/global_config.yaml
```

#### 4. 输出异常

**可能原因**：
- 字符编码问题
- 输出目标应用限制
- 打字速度过快

**解决方案**：
```yaml
# 调整配置文件
performance:
  typing_speed: 0.05  # 降低打字速度
  chunk_output_delay: 0.1  # 增加延迟
```

### 调试模式

启用详细日志：

```bash
# 启用调试模式
python main.py --debug

# 查看详细日志
tail -f prompt_manager.log | grep DEBUG
```

### 配置验证

```bash
# 验证配置文件语法
python -c "
import yaml
with open('config/global_config.yaml') as f:
    yaml.safe_load(f)
print('配置文件语法正确')
"
```

## ⚡ 性能优化

### 响应时间优化

确保快捷键响应时间 < 500ms：

```yaml
# config/global_config.yaml
performance:
  typing_speed: 0.01        # 降低延迟
  chunk_output_delay: 0.02  # 减少输出延迟
  timeout: 10               # 减少超时时间
  
logging:
  level: WARNING  # 减少日志输出
```

### 内存使用优化

```python
# 清理旧日志文件
python -c "
from main import PromptManager
manager = PromptManager()
manager.cleanup_old_logs(days=7)
"
```

### 模板缓存

程序会自动缓存模板文件，提高加载速度：

- 模板文件修改时自动重载
- 支持热重载配置
- 智能缓存策略

## ❓ 常见问题

### Q: 如何添加新的AI模型？

A: 在 `modules/model_client.py` 中添加新的客户端类：

```python
class NewModelClient(BaseModelClient):
    def __init__(self, api_key: str):
        super().__init__(ModelType.NEW_MODEL, api_key)
    
    def send_request(self, request: ModelRequest) -> ModelResponse:
        # 实现API调用逻辑
        pass
```

### Q: 如何备份配置？

A: 程序会自动创建配置备份：

```bash
# 手动备份
cp config/global_config.yaml config/global_config.yaml.backup
cp config/hotkey_mapping.yaml config/hotkey_mapping.yaml.backup
```

### Q: 如何批量处理文本？

A: 创建批处理脚本：

```python
from modules import TextProcessor

processor = TextProcessor()
texts = ["文本1", "文本2", "文本3"]

for text in texts:
    result = processor.insert_text_into_template("summarize.md", text)
    print(result['processed_content'])
```

### Q: 如何自定义输出格式？

A: 修改模板文件中的输出格式：

```markdown
---
model: deepseek-chat
---

请按以下格式输出：

# 分析结果

## 原文
{{text}}

## 总结
[在此提供总结]

## 建议
[在此提供建议]
```

### Q: 如何处理长文本？

A: 调整模型参数：

```yaml
---
model: deepseek-chat
max_tokens: 4000
temperature: 0.5
---

# 长文本处理模板

对于以下长文本，请分段分析：

{{text}}
```

### Q: 如何设置代理？

A: 设置环境变量：

```bash
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
python main.py
```

### Q: 如何禁用某个快捷键？

A: 在配置文件中注释或删除对应行：

```yaml
hotkey_mappings:
  'ctrl+alt+cmd+1': 'summarize.md'
  # 'ctrl+alt+cmd+2': 'translate.md'  # 已禁用
  'ctrl+alt+cmd+3': 'grammar_check.md'
```

## 📞 技术支持

如果遇到问题，请按以下步骤：

1. **查看日志文件**：`prompt_manager.log`
2. **检查配置文件**：确保语法正确
3. **验证权限设置**：特别是macOS系统
4. **重启程序**：使用调试模式
5. **提交Issue**：包含日志和配置信息

## 🔄 更新说明

### 版本检查
```bash
python main.py --version
```

### 更新步骤
```bash
# 备份配置
cp -r config config_backup

# 更新代码
git pull origin main

# 更新依赖
uv sync

# 重启程序
python main.py
```

---

**注意**：首次使用请仔细阅读配置说明，确保API密钥和权限设置正确。 