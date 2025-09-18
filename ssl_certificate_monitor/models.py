"""
数据模型定义
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


@dataclass
class CertificateInfo:
    """SSL证书信息"""
    domain: str
    expiry_date: Optional[datetime]
    days_until_expiry: int
    issuer: str
    is_valid: bool
    error_message: Optional[str] = None
    
    @property
    def is_expiring_soon(self) -> bool:
        """判断是否即将过期（30天内）"""
        return 0 <= self.days_until_expiry <= 30
    
    @property
    def is_expired(self) -> bool:
        """判断是否已过期"""
        return self.days_until_expiry < 0


@dataclass
class CheckResult:
    """检查结果统计"""
    total_domains: int
    successful_checks: int
    failed_checks: int
    expiring_domains: List[CertificateInfo]
    expired_domains: List[CertificateInfo]
    errors: List[str]
    execution_time: float