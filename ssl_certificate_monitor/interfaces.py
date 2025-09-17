"""
服务接口定义
"""
from abc import ABC, abstractmethod
from typing import List
from .models import CertificateInfo


class DomainConfigManagerInterface(ABC):
    """域名配置管理器接口"""
    
    @abstractmethod
    def get_domains(self) -> List[str]:
        """获取域名列表"""
        pass
    
    @abstractmethod
    def validate_domain(self, domain: str) -> bool:
        """验证域名格式"""
        pass


class SSLCertificateCheckerInterface(ABC):
    """SSL证书检查器接口"""
    
    @abstractmethod
    def check_certificate(self, domain: str) -> CertificateInfo:
        """检查单个域名的SSL证书"""
        pass


class NotificationServiceInterface(ABC):
    """通知服务接口"""
    
    @abstractmethod
    def send_expiry_notification(self, expiring_domains: List[CertificateInfo]) -> bool:
        """发送证书过期通知"""
        pass
    
    @abstractmethod
    def format_notification_content(self, domains: List[CertificateInfo]) -> str:
        """格式化通知内容"""
        pass


class LoggerServiceInterface(ABC):
    """日志服务接口"""
    
    @abstractmethod
    def log_check_start(self, domain_count: int):
        """记录检查开始"""
        pass
    
    @abstractmethod
    def log_certificate_info(self, domain: str, cert_info: CertificateInfo):
        """记录证书信息"""
        pass
    
    @abstractmethod
    def log_error(self, domain: str, error: Exception):
        """记录错误信息"""
        pass