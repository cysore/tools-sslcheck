# API文档

本文档描述了SSL证书监控系统的内部API和接口。

## Lambda函数接口

### lambda_handler

Lambda函数的主入口点。

**函数签名**：
```python
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]
```

**参数**：
- `event`: EventBridge触发事件（通常为空对象 `{}`）
- `context`: Lambda运行时上下文

**返回值**：
```json
{
    "statusCode": 200,
    "body": {
        "message": "SSL Certificate Monitor executed successfully",
        "summary": {
            "total_domains": 5,
            "successful_checks": 4,
            "failed_checks": 1,
            "expired_certificates": 0,
            "expiring_certificates": 2,
            "execution_time_seconds": 45.2,
            "success_rate": 0.8
        },
        "expired_domains": [],
        "expiring_domains": ["example.com", "test.org"],
        "errors": ["Connection failed for invalid.com"],
        "timestamp": "2024-01-15T09:00:00.000Z"
    }
}
```

**错误响应**：
```json
{
    "statusCode": 500,
    "body": {
        "message": "SSL Certificate Monitor encountered a critical error",
        "error": "Configuration validation failed",
        "timestamp": "2024-01-15T09:00:00.000Z"
    }
}
```

## 核心服务接口

### SSLCertificateChecker

SSL证书检查服务。

#### 构造函数
```python
def __init__(self, timeout: int = 10, port: int = 443)
```

**参数**：
- `timeout`: 连接超时时间（秒），默认10秒
- `port`: SSL端口，默认443

#### check_certificate

检查单个域名的SSL证书。

```python
def check_certificate(self, domain: str) -> CertificateInfo
```

**参数**：
- `domain`: 要检查的域名

**返回值**：`CertificateInfo` 对象

**示例**：
```python
checker = SSLCertificateChecker(timeout=15)
cert_info = checker.check_certificate("example.com")
print(f"域名: {cert_info.domain}")
print(f"过期时间: {cert_info.expiry_date}")
print(f"剩余天数: {cert_info.days_until_expiry}")
```

### DomainConfigManager

域名配置管理服务。

#### 构造函数
```python
def __init__(self, env_var_name: str = "DOMAINS")
```

**参数**：
- `env_var_name`: 环境变量名称，默认"DOMAINS"

#### get_domains

获取域名列表。

```python
def get_domains(self) -> List[str]
```

**返回值**：域名字符串列表

#### validate_domain

验证域名格式。

```python
def validate_domain(self, domain: str) -> bool
```

**参数**：
- `domain`: 要验证的域名

**返回值**：布尔值，表示域名是否有效

### SNSNotificationService

SNS通知服务。

#### 构造函数
```python
def __init__(self, topic_arn: Optional[str] = None, region_name: str = 'us-east-1')
```

**参数**：
- `topic_arn`: SNS主题ARN，如果为None则从环境变量读取
- `region_name`: AWS区域名称

#### send_expiry_notification

发送证书过期通知。

```python
def send_expiry_notification(self, expiring_domains: List[CertificateInfo]) -> bool
```

**参数**：
- `expiring_domains`: 即将过期的证书列表

**返回值**：布尔值，表示发送是否成功

#### format_notification_content

格式化通知内容。

```python
def format_notification_content(self, domains: List[CertificateInfo]) -> str
```

**参数**：
- `domains`: 证书信息列表

**返回值**：格式化的通知内容字符串

### LoggerService

日志服务。

#### 构造函数
```python
def __init__(self, logger_name: str = "ssl_certificate_monitor", log_level: Optional[str] = None)
```

**参数**：
- `logger_name`: 日志器名称
- `log_level`: 日志级别，如果为None则从环境变量读取

#### 主要方法

```python
def log_check_start(self, domain_count: int)
def log_certificate_info(self, domain: str, cert_info: CertificateInfo)
def log_error(self, domain: str, error: Exception)
def log_check_end(self)
def get_execution_summary(self) -> Dict[str, Any]
```

## 数据模型

### CertificateInfo

SSL证书信息数据类。

```python
@dataclass
class CertificateInfo:
    domain: str                           # 域名
    expiry_date: datetime                 # 过期时间
    days_until_expiry: int               # 剩余天数
    issuer: str                          # 证书颁发者
    is_valid: bool                       # 是否有效
    error_message: Optional[str] = None   # 错误消息
```

**属性方法**：
```python
@property
def is_expiring_soon(self) -> bool:
    """判断是否即将过期（30天内）"""
    return 0 <= self.days_until_expiry <= 30

@property
def is_expired(self) -> bool:
    """判断是否已过期"""
    return self.days_until_expiry < 0
```

### CheckResult

检查结果数据类。

```python
@dataclass
class CheckResult:
    total_domains: int                    # 总域名数
    successful_checks: int                # 成功检查数
    failed_checks: int                    # 失败检查数
    expiring_domains: List[CertificateInfo]  # 即将过期的域名
    expired_domains: List[CertificateInfo]   # 已过期的域名
    errors: List[str]                     # 错误列表
    execution_time: float                 # 执行时间（秒）
```

## 错误处理接口

### NetworkErrorHandler

网络错误处理器。

#### with_retry

带重试机制执行函数。

```python
def with_retry(self, func: Callable, *args, **kwargs) -> Any
```

**参数**：
- `func`: 要执行的函数
- `*args`: 函数参数
- `**kwargs`: 函数关键字参数

**返回值**：函数执行结果

**异常**：重试次数用尽后的最后一个异常

#### handle_ssl_connection_error

处理SSL连接错误。

```python
def handle_ssl_connection_error(self, domain: str, error: Exception) -> Dict[str, Any]
```

**参数**：
- `domain`: 域名
- `error`: 异常对象

**返回值**：错误处理结果字典

### ConfigValidator

配置验证器。

#### validate_all_configurations

验证所有配置。

```python
def validate_all_configurations(self) -> Dict[str, Any]
```

**返回值**：验证结果字典
```json
{
    "is_valid": true,
    "errors": [],
    "warnings": [],
    "configurations": {
        "environment": {...},
        "domains": {...},
        "sns": {...},
        "lambda": {...}
    }
}
```

## 环境变量接口

系统通过环境变量进行配置：

| 变量名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `DOMAINS` | string | 是 | - | 域名列表（逗号分隔） |
| `SNS_TOPIC_ARN` | string | 是 | - | SNS主题ARN |
| `LOG_LEVEL` | string | 否 | "INFO" | 日志级别 |

### 环境变量验证

```python
from ssl_certificate_monitor.services.config_validator import ConfigValidator

validator = ConfigValidator()
result = validator.validate_all_configurations()

if not result['is_valid']:
    print("配置验证失败:")
    for error in result['errors']:
        print(f"  - {error}")
```

## 扩展接口

### 自定义通知服务

实现 `NotificationServiceInterface` 接口：

```python
from ssl_certificate_monitor.interfaces import NotificationServiceInterface

class CustomNotificationService(NotificationServiceInterface):
    def send_expiry_notification(self, expiring_domains: List[CertificateInfo]) -> bool:
        # 实现自定义通知逻辑
        pass
    
    def format_notification_content(self, domains: List[CertificateInfo]) -> str:
        # 实现自定义格式化逻辑
        pass
```

### 自定义SSL检查器

扩展 `SSLCertificateChecker` 类：

```python
from ssl_certificate_monitor.services.ssl_checker import SSLCertificateChecker

class CustomSSLChecker(SSLCertificateChecker):
    def __init__(self, custom_timeout: int = 20):
        super().__init__(timeout=custom_timeout)
    
    def check_certificate(self, domain: str) -> CertificateInfo:
        # 添加自定义检查逻辑
        result = super().check_certificate(domain)
        # 进行额外处理
        return result
```

## 测试接口

### 单元测试辅助

```python
from ssl_certificate_monitor.models import CertificateInfo
from datetime import datetime, timezone, timedelta

def create_test_certificate(domain: str, days_until_expiry: int) -> CertificateInfo:
    """创建测试用的证书信息"""
    expiry_date = datetime.now(timezone.utc) + timedelta(days=days_until_expiry)
    return CertificateInfo(
        domain=domain,
        expiry_date=expiry_date,
        days_until_expiry=days_until_expiry,
        issuer="Test CA",
        is_valid=True
    )
```

### 集成测试

```python
import os
from unittest.mock import patch
from ssl_certificate_monitor.lambda_handler import lambda_handler

def test_lambda_integration():
    with patch.dict(os.environ, {
        'DOMAINS': 'example.com',
        'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:test-topic'
    }):
        response = lambda_handler({}, None)
        assert response['statusCode'] == 200
```

## 性能监控接口

### 执行统计

```python
from ssl_certificate_monitor.services.logger import LoggerService

logger_service = LoggerService()
# ... 执行检查 ...
summary = logger_service.get_execution_summary()

print(f"执行时间: {summary['duration_seconds']}秒")
print(f"成功率: {summary['success_rate']:.1%}")
```

### 批量处理

```python
from ssl_certificate_monitor.lambda_handler import SSLCertificateMonitor

monitor = SSLCertificateMonitor()
domains = ['example.com', 'test.org', 'mysite.net']

# 批量检查（批量大小为5）
results = monitor._check_certificates_batch(domains, batch_size=5)
```

## 错误代码

系统使用以下错误代码：

| 代码 | 描述 | 处理建议 |
|------|------|----------|
| `DOMAIN_RESOLUTION_FAILED` | DNS解析失败 | 检查域名拼写 |
| `SSL_CONNECTION_TIMEOUT` | SSL连接超时 | 增加超时时间 |
| `CERTIFICATE_EXPIRED` | 证书已过期 | 更新证书 |
| `CERTIFICATE_INVALID` | 证书无效 | 检查证书配置 |
| `SNS_PUBLISH_FAILED` | SNS发布失败 | 检查权限和配置 |
| `CONFIG_VALIDATION_FAILED` | 配置验证失败 | 检查环境变量 |

## 版本兼容性

### API版本

当前API版本：`v1.0.0`

### 向后兼容性

- 所有公共接口保持向后兼容
- 新功能通过可选参数添加
- 废弃的功能会提前通知

### 升级指南

从旧版本升级时：

1. 检查环境变量配置
2. 更新Lambda函数代码
3. 验证通知配置
4. 测试完整流程

## 示例代码

### 完整使用示例

```python
import os
from ssl_certificate_monitor.lambda_handler import SSLCertificateMonitor

# 设置环境变量
os.environ['DOMAINS'] = 'example.com,test.org'
os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:alerts'
os.environ['LOG_LEVEL'] = 'INFO'

# 创建监控器
monitor = SSLCertificateMonitor()

# 执行检查
result = monitor.execute()

# 输出结果
print(f"检查了 {result.total_domains} 个域名")
print(f"成功: {result.successful_checks}, 失败: {result.failed_checks}")
print(f"即将过期: {len(result.expiring_domains)} 个")
print(f"已过期: {len(result.expired_domains)} 个")
```

### 自定义检查器示例

```python
from ssl_certificate_monitor.services.ssl_checker import SSLCertificateChecker
from ssl_certificate_monitor.services.logger import LoggerService

# 创建自定义检查器
checker = SSLCertificateChecker(timeout=20, port=443)
logger = LoggerService(log_level="DEBUG")

# 检查单个域名
domain = "example.com"
logger.log_check_start(1)

try:
    cert_info = checker.check_certificate(domain)
    logger.log_certificate_info(domain, cert_info)
    
    if cert_info.is_expiring_soon:
        print(f"警告: {domain} 的证书将在 {cert_info.days_until_expiry} 天后过期")
    
except Exception as e:
    logger.log_error(domain, e)
    print(f"检查失败: {e}")

finally:
    logger.log_check_end()
```

这个API文档提供了系统所有公共接口的详细说明，帮助开发者理解和扩展SSL证书监控系统。