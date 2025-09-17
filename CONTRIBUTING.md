# 贡献指南

感谢您对SSL证书监控系统的关注！我们欢迎各种形式的贡献。

## 贡献方式

### 报告问题

如果您发现了bug或有功能建议：

1. 搜索现有的[Issues](../../issues)，确保问题未被报告
2. 使用问题模板创建新的Issue
3. 提供详细的重现步骤和环境信息

### 提交代码

1. **Fork项目**到您的GitHub账户
2. **创建功能分支**：`git checkout -b feature/your-feature-name`
3. **编写代码**并遵循项目规范
4. **添加测试**确保代码质量
5. **提交更改**：`git commit -m "Add: your feature description"`
6. **推送分支**：`git push origin feature/your-feature-name`
7. **创建Pull Request**

## 开发环境设置

### 环境要求

- Python 3.9+
- AWS CLI 2.0+
- Git

### 本地开发设置

```bash
# 1. 克隆项目
git clone https://github.com/your-username/ssl-certificate-monitor.git
cd ssl-certificate-monitor

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行测试
python -m pytest tests/ -v

# 5. 检查代码风格
flake8 ssl_certificate_monitor/
black ssl_certificate_monitor/ --check
```

### 开发工具

推荐使用以下工具：

```bash
# 代码格式化
pip install black isort

# 代码检查
pip install flake8 mypy

# 测试覆盖率
pip install pytest-cov
```

## 代码规范

### Python代码风格

我们遵循[PEP 8](https://pep8.org/)代码风格指南：

```bash
# 使用black格式化代码
black ssl_certificate_monitor/ tests/

# 使用isort整理导入
isort ssl_certificate_monitor/ tests/

# 使用flake8检查代码
flake8 ssl_certificate_monitor/ tests/
```

### 类型提示

所有公共函数和方法都应该包含类型提示：

```python
from typing import List, Dict, Optional
from datetime import datetime

def check_certificate(self, domain: str) -> CertificateInfo:
    """检查SSL证书"""
    pass

def get_domains(self) -> List[str]:
    """获取域名列表"""
    pass
```

### 文档字符串

使用Google风格的文档字符串：

```python
def example_function(param1: str, param2: int = 10) -> bool:
    """
    示例函数说明
    
    Args:
        param1: 第一个参数说明
        param2: 第二个参数说明，默认值为10
        
    Returns:
        bool: 返回值说明
        
    Raises:
        ValueError: 参数无效时抛出
        ConnectionError: 连接失败时抛出
    """
    pass
```

### 错误处理

```python
# 好的错误处理
try:
    result = risky_operation()
except SpecificException as e:
    logger.error(f"操作失败: {str(e)}")
    return default_value
except Exception as e:
    logger.error(f"未知错误: {str(e)}")
    raise

# 避免的做法
try:
    result = risky_operation()
except:  # 不要使用裸露的except
    pass
```

## 测试规范

### 测试结构

```
tests/
├── test_unit/              # 单元测试
│   ├── test_ssl_checker.py
│   ├── test_domain_config.py
│   └── ...
├── test_integration/       # 集成测试
│   ├── test_end_to_end.py
│   └── ...
└── test_performance/       # 性能测试
    ├── test_load.py
    └── ...
```

### 测试命名

```python
class TestSSLCertificateChecker:
    def test_check_certificate_success(self):
        """测试成功的证书检查"""
        pass
    
    def test_check_certificate_timeout_error(self):
        """测试超时错误处理"""
        pass
    
    def test_check_certificate_invalid_domain(self):
        """测试无效域名处理"""
        pass
```

### 测试覆盖率

目标测试覆盖率：**90%以上**

```bash
# 运行覆盖率测试
python -m pytest tests/ --cov=ssl_certificate_monitor --cov-report=html --cov-report=term

# 查看覆盖率报告
open htmlcov/index.html
```

### Mock使用

```python
from unittest.mock import patch, MagicMock

class TestExample:
    @patch('ssl_certificate_monitor.services.ssl_checker.socket.create_connection')
    def test_with_mock(self, mock_connection):
        """使用mock的测试示例"""
        mock_connection.return_value.__enter__.return_value = MagicMock()
        # 测试逻辑
```

## 提交规范

### 提交消息格式

使用[Conventional Commits](https://www.conventionalcommits.org/)格式：

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**类型**：
- `feat`: 新功能
- `fix`: 错误修复
- `docs`: 文档更新
- `style`: 代码格式化
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建过程或辅助工具的变动

**示例**：
```
feat(ssl-checker): add retry mechanism for network errors

Add exponential backoff retry logic to handle temporary network failures.
This improves the reliability of SSL certificate checking.

Closes #123
```

### Pull Request规范

#### PR标题

使用清晰、描述性的标题：
- ✅ `feat: add batch processing for large domain lists`
- ✅ `fix: handle SSL handshake timeout errors`
- ❌ `update code`
- ❌ `bug fix`

#### PR描述

使用PR模板：

```markdown
## 变更类型
- [ ] Bug修复
- [ ] 新功能
- [ ] 重大变更
- [ ] 文档更新

## 变更描述
[详细描述您的更改]

## 测试
- [ ] 添加了新的测试
- [ ] 所有现有测试通过
- [ ] 手动测试通过

## 检查清单
- [ ] 代码遵循项目风格指南
- [ ] 自我审查了代码
- [ ] 添加了必要的注释
- [ ] 更新了相关文档
- [ ] 没有引入新的警告

## 相关Issue
Closes #[issue number]
```

## 发布流程

### 版本号规范

使用[语义化版本](https://semver.org/)：

- `MAJOR.MINOR.PATCH`
- 例如：`1.2.3`

**版本递增规则**：
- `MAJOR`: 不兼容的API更改
- `MINOR`: 向后兼容的功能添加
- `PATCH`: 向后兼容的错误修复

### 发布检查清单

发布新版本前：

- [ ] 所有测试通过
- [ ] 文档已更新
- [ ] 变更日志已更新
- [ ] 版本号已更新
- [ ] 创建了Git标签
- [ ] 部署测试通过

## 社区准则

### 行为准则

我们致力于为每个人提供友好、安全和欢迎的环境：

- 使用友好和包容的语言
- 尊重不同的观点和经验
- 优雅地接受建设性批评
- 关注对社区最有利的事情
- 对其他社区成员表示同理心

### 沟通渠道

- **GitHub Issues**: 错误报告和功能请求
- **GitHub Discussions**: 一般讨论和问题
- **Pull Requests**: 代码审查和讨论

## 认可贡献者

我们感谢所有贡献者的努力！贡献者将被列在：

- README.md的贡献者部分
- 发布说明中
- 项目网站上（如果有）

### 贡献类型

我们认可以下类型的贡献：

- 💻 代码贡献
- 📖 文档改进
- 🐛 错误报告
- 💡 功能建议
- 🎨 设计改进
- 🌍 翻译工作
- 📢 推广宣传

感谢您的贡献！