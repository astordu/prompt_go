# 配置示例文档

## 📋 目录

- [基础配置](#基础配置)
- [高级配置](#高级配置)
- [性能优化配置](#性能优化配置)
- [多模型配置](#多模型配置)
- [自定义快捷键](#自定义快捷键)
- [环境特定配置](#环境特定配置)
- [故障排除配置](#故障排除配置)

## 🔧 基础配置

### 1. 最小配置示例

**config/global_config.yaml**
```yaml
# 最简配置 - 仅配置一个API
api:
  deepseek:
    key: 'sk-your-deepseek-api-key'
    model: deepseek-chat
```

**config/hotkey_mapping.yaml**
```yaml
# 最简快捷键配置
hotkey_mappings:
  'ctrl+alt+cmd+1': 'summarize.md'
```

### 2. 标准配置示例

**config/global_config.yaml**
```yaml
# 标准配置 - 包含主要功能
api:
  deepseek:
    base_url: https://api.deepseek.com
    key: 'sk-your-deepseek-api-key'
    model: deepseek-chat
  
  kimi:
    base_url: https://api.moonshot.cn
    key: 'sk-your-kimi-api-key'
    model: moonshot-v1-8k

logging:
  level: INFO
  file: prompt_manager.log
  max_size: 10485760  # 10MB
  backup_count: 5

performance:
  typing_speed: 0.01
  timeout: 30
  max_tokens: 2000
```

**config/hotkey_mapping.yaml**
```yaml
# 标准快捷键配置
hotkey_mappings:
  'ctrl+alt+cmd+1': 'summarize.md'
  'ctrl+alt+cmd+2': 'translate.md'
  'ctrl+alt+cmd+3': 'grammar_check.md'
  'ctrl+alt+cmd+4': 'explain.md'
  'ctrl+alt+cmd+5': 'improve.md'

settings:
  enable_notifications: true
  auto_reload: true
  debounce_time: 0.5
```

## ⚡ 性能优化配置

### 1. 高性能配置

**适用场景**：需要快速响应，对延迟敏感

```yaml
# config/global_config.yaml
api:
  deepseek:
    base_url: https://api.deepseek.com
    key: 'sk-your-api-key'
    model: deepseek-chat

logging:
  level: WARNING  # 减少日志输出
  file: prompt_manager.log
  max_size: 5242880  # 5MB
  backup_count: 2

performance:
  typing_speed: 0.005      # 更快的打字速度
  chunk_output_delay: 0.01 # 减少流式输出延迟
  timeout: 15              # 减少超时时间
  max_tokens: 1500         # 减少token数量
  max_output_length: 2000  # 限制输出长度

# 缓存设置
cache:
  template_cache_size: 50
  config_cache_ttl: 300
```

### 2. 低延迟配置

**适用场景**：要求响应时间 < 300ms

```yaml
# config/global_config.yaml
performance:
  typing_speed: 0.002      # 极快打字速度
  chunk_output_delay: 0.005 # 最小延迟
  timeout: 10              # 快速超时
  max_tokens: 1000         # 限制输出
  buffer_size: 1024        # 优化缓冲区
  
  # 预加载设置
  preload_templates: true
  preload_models: true
  warm_up_requests: 2

# 简化日志
logging:
  level: ERROR
  file: /dev/null  # 禁用文件日志（Linux/macOS）
```

## 🤖 多模型配置

### 1. 多API服务商配置

```yaml
# config/global_config.yaml
api:
  # Deepseek配置
  deepseek:
    base_url: https://api.deepseek.com
    key: 'sk-deepseek-key'
    model: deepseek-chat
    max_tokens: 2000
    temperature: 0.7
    
  # Kimi配置
  kimi:
    base_url: https://api.moonshot.cn
    key: 'sk-kimi-key'
    model: moonshot-v1-8k
    max_tokens: 4000
    temperature: 0.5
    
  # OpenAI配置（示例）
  openai:
    base_url: https://api.openai.com
    key: 'sk-openai-key'
    model: gpt-3.5-turbo
    max_tokens: 1500
    temperature: 0.6

# 模型选择策略
model_selection:
  default: deepseek
  fallback_order: [deepseek, kimi, openai]
  load_balancing: round_robin  # round_robin, random, priority
```

### 2. 任务特定模型配置

```yaml
# config/model_routing.yaml
# 根据任务类型自动选择最适合的模型

task_routing:
  summarize: deepseek      # 总结任务用deepseek
  translate: kimi          # 翻译任务用kimi
  code_review: deepseek    # 代码审查用deepseek
  creative_writing: openai # 创意写作用openai
  
model_configs:
  deepseek:
    temperature: 0.3  # 更保守的参数
    max_tokens: 1500
    
  kimi:
    temperature: 0.2  # 翻译需要准确性
    max_tokens: 2000
    
  openai:
    temperature: 0.8  # 创意写作需要更多随机性
    max_tokens: 2500
```

## ⌨️ 自定义快捷键配置

### 1. 工作流程快捷键

**适用场景**：日常工作中的常用操作

```yaml
# config/hotkey_mapping.yaml
hotkey_mappings:
  # 文档处理
  'ctrl+alt+cmd+1': 'summarize.md'
  'ctrl+alt+cmd+2': 'translate_en.md'
  'ctrl+alt+cmd+3': 'translate_cn.md'
  'ctrl+alt+cmd+4': 'proofread.md'
  
  # 代码相关
  'ctrl+alt+cmd+q': 'code_review.md'
  'ctrl+alt+cmd+w': 'add_comments.md'
  'ctrl+alt+cmd+e': 'explain_code.md'
  'ctrl+alt+cmd+r': 'refactor_suggest.md'
  
  # 写作辅助
  'ctrl+shift+cmd+1': 'polish_writing.md'
  'ctrl+shift+cmd+2': 'expand_ideas.md'
  'ctrl+shift+cmd+3': 'email_format.md'

settings:
  enable_notifications: true
  notification_duration: 3000  # 3秒
  auto_reload: true
  debounce_time: 0.3
```

### 2. 专业领域快捷键

**适用场景**：特定专业领域的用户

```yaml
# config/hotkey_mapping.yaml - 学术研究版
hotkey_mappings:
  # 学术写作
  'ctrl+alt+cmd+1': 'academic_summary.md'
  'ctrl+alt+cmd+2': 'literature_review.md'
  'ctrl+alt+cmd+3': 'hypothesis_generate.md'
  'ctrl+alt+cmd+4': 'methodology_review.md'
  'ctrl+alt+cmd+5': 'citation_format.md'
  
  # 数据分析
  'ctrl+alt+cmd+6': 'data_interpret.md'
  'ctrl+alt+cmd+7': 'statistical_check.md'
  'ctrl+alt+cmd+8': 'research_questions.md'
  'ctrl+alt+cmd+9': 'conclusion_draft.md'

# 学术特定设置
settings:
  enable_notifications: false  # 学术环境可能需要安静
  auto_reload: true
  debounce_time: 1.0  # 更长的防抖时间，适合深度思考
  
conflict_resolution:
  strategy: 'manual'  # 学术用户可能需要精确控制
  backup_on_change: true
```

## 🌍 环境特定配置

### 1. 开发环境配置

```yaml
# config/global_config.yaml - 开发环境
api:
  deepseek:
    base_url: https://api.deepseek.com
    key: 'sk-dev-key'
    model: deepseek-chat

logging:
  level: DEBUG  # 开发时需要详细日志
  file: dev_prompt_manager.log
  max_size: 52428800  # 50MB，开发时需要更多日志
  backup_count: 10
  auto_cleanup: false  # 开发时保留所有日志

performance:
  typing_speed: 0.05  # 开发时可以慢一些，便于调试
  timeout: 60         # 更长的超时时间
  max_tokens: 4000    # 开发时可能需要更详细的输出

# 开发特定设置
development:
  mock_api_calls: false     # 是否模拟API调用
  cache_responses: true     # 缓存响应便于测试
  debug_mode: true          # 启用调试模式
  profile_performance: true # 性能分析
```

### 2. 生产环境配置

```yaml
# config/global_config.yaml - 生产环境
api:
  deepseek:
    base_url: https://api.deepseek.com
    key: '${DEEPSEEK_API_KEY}'  # 使用环境变量
    model: deepseek-chat
  
  kimi:
    base_url: https://api.moonshot.cn
    key: '${KIMI_API_KEY}'
    model: moonshot-v1-8k

logging:
  level: INFO
  file: /var/log/prompt_manager/app.log  # 标准日志位置
  max_size: 10485760
  backup_count: 5
  auto_cleanup: true
  cleanup_days: 7

performance:
  typing_speed: 0.01
  timeout: 30
  max_tokens: 2000

# 生产环境安全设置
security:
  api_key_encryption: true
  log_sensitive_data: false
  rate_limiting: true
  max_requests_per_minute: 60

# 监控设置
monitoring:
  enable_metrics: true
  metrics_port: 9090
  health_check_endpoint: '/health'
```

### 3. 团队共享配置

```yaml
# config/global_config.yaml - 团队版
api:
  # 团队共享的API配置
  shared_deepseek:
    base_url: https://api.deepseek.com
    key: '${TEAM_DEEPSEEK_KEY}'
    model: deepseek-chat
    rate_limit: 1000  # 团队级别限制

# 团队设置
team:
  organization: 'your-team'
  shared_templates: true
  template_sync_url: 'https://your-server.com/templates'
  user_analytics: true

# 用户个人设置
user:
  name: '${USER_NAME}'
  role: '${USER_ROLE}'
  custom_shortcuts: true
  personal_templates_dir: 'personal_templates'

logging:
  level: INFO
  file: 'logs/${USER_NAME}_prompt_manager.log'
  include_user_id: true
```

## 🔧 故障排除配置

### 1. 诊断配置

**适用场景**：出现问题时的诊断配置

```yaml
# config/global_config.yaml - 诊断模式
api:
  deepseek:
    base_url: https://api.deepseek.com
    key: 'sk-your-key'
    model: deepseek-chat

logging:
  level: DEBUG
  file: diagnostic_prompt_manager.log
  max_size: 104857600  # 100MB
  backup_count: 20
  include_stack_trace: true
  log_api_requests: true   # 记录所有API请求
  log_api_responses: true  # 记录所有API响应

performance:
  typing_speed: 0.1  # 很慢的打字速度，便于观察
  timeout: 120       # 很长的超时时间
  enable_profiling: true
  detailed_timing: true

# 诊断特定设置
diagnostics:
  capture_screenshots: true
  record_key_events: true
  monitor_memory_usage: true
  track_api_latency: true
  validate_all_inputs: true
```

### 2. 网络问题配置

**适用场景**：网络不稳定的环境

```yaml
# config/global_config.yaml - 网络优化
api:
  deepseek:
    base_url: https://api.deepseek.com
    key: 'sk-your-key'
    model: deepseek-chat
    
# 网络优化设置
network:
  retry_attempts: 5
  retry_delay: 2.0
  exponential_backoff: true
  connection_timeout: 30
  read_timeout: 60
  proxy_url: 'http://proxy.company.com:8080'  # 如果需要代理
  
  # 连接池设置
  pool_connections: 10
  pool_maxsize: 20
  max_retries: 3

performance:
  timeout: 90  # 网络不好时需要更长超时
  chunk_size: 512  # 减小数据块大小
  enable_compression: true
```

## 📊 监控和日志配置

### 1. 详细监控配置

```yaml
# config/global_config.yaml - 监控版
logging:
  level: INFO
  file: prompt_manager.log
  max_size: 10485760
  backup_count: 5
  
  # 结构化日志
  format: json
  include_fields:
    - timestamp
    - level
    - message
    - user_id
    - template_name
    - response_time
    - api_model
    - token_count

# 指标收集
metrics:
  enable: true
  collection_interval: 60  # 秒
  export_format: prometheus
  
  tracked_metrics:
    - api_request_count
    - api_response_time
    - template_usage_count
    - error_rate
    - user_satisfaction
    - memory_usage
    - cpu_usage

# 告警设置
alerts:
  enable: true
  
  rules:
    - name: high_error_rate
      condition: error_rate > 0.1
      action: email
      
    - name: slow_response
      condition: avg_response_time > 5000  # 5秒
      action: slack
      
    - name: api_quota_exceeded
      condition: api_requests > daily_limit * 0.9
      action: notification
```

## 🎨 自定义配置模板

### 1. 最小启动模板

```bash
#!/bin/bash
# quick_setup.sh - 快速设置脚本

# 创建基本配置
mkdir -p config prompt

# 生成最小配置
cat > config/global_config.yaml << EOF
api:
  deepseek:
    key: '${DEEPSEEK_API_KEY:-sk-your-key-here}'
    model: deepseek-chat
logging:
  level: INFO
EOF

cat > config/hotkey_mapping.yaml << EOF
hotkey_mappings:
  'ctrl+alt+cmd+1': 'summarize.md'
EOF

# 创建基本模板
cat > prompt/summarize.md << 'EOF'
请总结以下内容：

{{text}}
EOF

echo "配置创建完成！请编辑 config/global_config.yaml 中的API密钥。"
```

### 2. 配置验证脚本

```python
#!/usr/bin/env python3
# validate_config.py - 配置验证脚本

import yaml
import sys
from pathlib import Path

def validate_config():
    """验证配置文件"""
    errors = []
    
    # 检查全局配置
    global_config_path = Path('config/global_config.yaml')
    if not global_config_path.exists():
        errors.append("config/global_config.yaml 不存在")
    else:
        try:
            with open(global_config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                
            # 验证API配置
            if 'api' not in config:
                errors.append("缺少API配置")
            else:
                for provider, settings in config['api'].items():
                    if 'key' not in settings:
                        errors.append(f"{provider} 缺少API密钥")
                    if settings.get('key', '').startswith('sk-your-'):
                        errors.append(f"{provider} 使用的是示例API密钥")
                        
        except yaml.YAMLError as e:
            errors.append(f"global_config.yaml 语法错误: {e}")
    
    # 检查快捷键配置
    hotkey_config_path = Path('config/hotkey_mapping.yaml')
    if hotkey_config_path.exists():
        try:
            with open(hotkey_config_path, 'r', encoding='utf-8') as f:
                yaml.safe_load(f)
        except yaml.YAMLError as e:
            errors.append(f"hotkey_mapping.yaml 语法错误: {e}")
    
    # 检查模板目录
    prompt_dir = Path('prompt')
    if not prompt_dir.exists():
        errors.append("prompt 目录不存在")
    elif not list(prompt_dir.glob('*.md')):
        errors.append("prompt 目录中没有模板文件")
    
    # 输出结果
    if errors:
        print("❌ 配置验证失败:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("✅ 配置验证通过!")

if __name__ == '__main__':
    validate_config()
```

---

## 📝 配置最佳实践

1. **安全性**：
   - 使用环境变量存储敏感信息
   - 定期轮换API密钥
   - 不要将密钥提交到版本控制

2. **性能**：
   - 根据实际需求调整打字速度
   - 合理设置超时时间
   - 启用适当的缓存

3. **可维护性**：
   - 使用注释说明配置用途
   - 保持配置文件结构清晰
   - 定期备份配置文件

4. **团队协作**：
   - 使用配置模板
   - 文档化自定义配置
   - 建立配置更新流程 