"""
项目初始化模块

负责在程序启动时自动创建必要的目录结构和示例文件
"""

import os
import logging
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


class ProjectInitializer:
    """项目初始化管理器"""
    
    def __init__(self, project_root: Optional[str] = None):
        """
        初始化项目初始化器
        
        Args:
            project_root: 项目根目录，如果为None则使用当前工作目录
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.prompt_dir = self.project_root / "prompt"
        self.config_dir = self.project_root / "config"
        
    def ensure_directories(self) -> bool:
        """
        确保必要的目录存在
        
        Returns:
            bool: 是否成功创建或验证了所有目录
        """
        directories = [
            self.prompt_dir,
            self.config_dir
        ]
        
        try:
            for directory in directories:
                if not directory.exists():
                    directory.mkdir(parents=True, exist_ok=True)
                    logger.info(f"创建目录: {directory}")
                else:
                    logger.debug(f"目录已存在: {directory}")
                    
            return True
            
        except Exception as e:
            logger.error(f"创建目录失败: {e}")
            return False
            
    def create_example_templates(self) -> bool:
        """
        创建示例提示词模板文件
        
        Returns:
            bool: 是否成功创建示例模板
        """
        example_templates = [
            {
                "filename": "translate.md",
                "content": self._get_translate_template()
            },
            {
                "filename": "summarize.md", 
                "content": self._get_summarize_template()
            },
            {
                "filename": "grammar_check.md",
                "content": self._get_grammar_check_template()
            }
        ]
        
        try:
            for template in example_templates:
                template_path = self.prompt_dir / template["filename"]
                
                # 只有在文件不存在时才创建
                if not template_path.exists():
                    with open(template_path, 'w', encoding='utf-8') as f:
                        f.write(template["content"])
                    logger.info(f"创建示例模板: {template_path}")
                else:
                    logger.debug(f"模板已存在: {template_path}")
                    
            return True
            
        except Exception as e:
            logger.error(f"创建示例模板失败: {e}")
            return False
            
    def _get_translate_template(self) -> str:
        """获取翻译模板内容"""
        return """model: deepseek
temperature: 0.3
max_tokens: 2000

---

你是一个专业的翻译助手。请将以下文本翻译成中文，保持原文的语气和格式：

{{input}}

请提供准确、自然的翻译，注意上下文的连贯性。"""

    def _get_summarize_template(self) -> str:
        """获取摘要模板内容"""
        return """model: kimi
temperature: 0.2
max_tokens: 1500

---

请为以下文本生成简洁、准确的摘要，突出主要观点和关键信息：

{{input}}

要求：
1. 摘要长度不超过原文的1/3
2. 保留核心信息和重要细节
3. 使用简洁清晰的语言"""

    def _get_grammar_check_template(self) -> str:
        """获取语法检查模板内容"""
        return """model: deepseek
temperature: 0.1
max_tokens: 2000

---

请检查以下文本的语法、拼写和表达，并提供改进建议：

{{input}}

请指出：
1. 语法错误并提供正确的表达
2. 拼写错误
3. 可以改进的表达方式
4. 提供修改后的完整文本"""

    def create_readme_if_needed(self) -> bool:
        """
        如果需要，创建prompt目录的README说明文件
        
        Returns:
            bool: 是否成功创建或验证了README文件
        """
        readme_path = self.prompt_dir / "README.md"
        
        try:
            if not readme_path.exists():
                readme_content = self._get_readme_content()
                with open(readme_path, 'w', encoding='utf-8') as f:
                    f.write(readme_content)
                logger.info(f"创建README文件: {readme_path}")
            else:
                logger.debug(f"README文件已存在: {readme_path}")
                
            return True
            
        except Exception as e:
            logger.error(f"创建README文件失败: {e}")
            return False
            
    def _get_readme_content(self) -> str:
        """获取README文件内容"""
        return """# 提示词模板目录

这个目录用于存储提示词模板文件，每个 `.md` 文件代表一个提示词模板。

## 模板文件格式

每个模板文件包含两部分，用 `---` 分隔：

### 第一部分：模型配置
```yaml
model: deepseek          # 使用的模型 (deepseek/kimi)
temperature: 0.3         # 温度参数 (0.0-1.0)
max_tokens: 2000        # 最大令牌数
```

### 第二部分：提示词内容
```
你是一个专业的助手。请处理以下内容：

{{input}}

请提供详细的回复。
```

## 占位符说明

- `{{input}}`: 选中的文本会自动插入到这个位置
- 每个模板只能包含一个 `{{input}}` 占位符

## 示例模板

- `translate.md`: 翻译助手
- `summarize.md`: 文本摘要
- `grammar_check.md`: 语法检查

## 使用方法

1. 创建新的 `.md` 文件
2. 按照格式编写模板内容
3. 在快捷键配置中设置映射关系
4. 使用快捷键调用模板处理选中文本

## 注意事项

- 文件名使用英文和下划线
- 确保模型名称正确 (deepseek/kimi)
- 模板内容要清晰具体
- 定期备份重要的模板文件
"""

    def initialize_project(self, create_examples: bool = True) -> bool:
        """
        完整的项目初始化
        
        Args:
            create_examples: 是否创建示例模板文件
            
        Returns:
            bool: 是否成功完成项目初始化
        """
        logger.info("开始项目初始化...")
        
        # 1. 创建必要的目录
        if not self.ensure_directories():
            logger.error("目录创建失败")
            return False
            
        # 2. 创建README文件
        if not self.create_readme_if_needed():
            logger.error("README文件创建失败")
            return False
            
        # 3. 如果需要，创建示例模板
        if create_examples:
            if not self.create_example_templates():
                logger.error("示例模板创建失败")
                return False
                
        logger.info("项目初始化完成")
        return True
        
    def get_prompt_files(self) -> List[Path]:
        """
        获取prompt目录下的所有.md文件
        
        Returns:
            List[Path]: .md文件路径列表
        """
        if not self.prompt_dir.exists():
            return []
            
        return list(self.prompt_dir.glob("*.md"))
        
    def validate_project_structure(self) -> bool:
        """
        验证项目结构是否完整
        
        Returns:
            bool: 项目结构是否有效
        """
        required_dirs = [self.prompt_dir, self.config_dir]
        
        for directory in required_dirs:
            if not directory.exists() or not directory.is_dir():
                logger.error(f"缺少必需的目录: {directory}")
                return False
                
        logger.info("项目结构验证通过")
        return True


def initialize_on_startup(project_root: Optional[str] = None, 
                         create_examples: bool = True) -> bool:
    """
    程序启动时的自动初始化函数
    
    Args:
        project_root: 项目根目录
        create_examples: 是否创建示例模板
        
    Returns:
        bool: 初始化是否成功
    """
    try:
        initializer = ProjectInitializer(project_root)
        return initializer.initialize_project(create_examples)
    except Exception as e:
        logger.error(f"启动时初始化失败: {e}")
        return False 