"""
证书过期计算服务
"""
from datetime import datetime, timezone, timedelta
from typing import List
from ..models import CertificateInfo


class ExpiryCalculator:
    """证书过期计算器"""
    
    def __init__(self, warning_days: int = 30):
        """
        初始化过期计算器
        
        Args:
            warning_days: 提前警告天数，默认30天
        """
        self.warning_days = warning_days
    
    def calculate_days_until_expiry(self, expiry_date: datetime) -> int:
        """
        计算距离过期的天数
        
        Args:
            expiry_date: 过期时间
            
        Returns:
            int: 剩余天数（负数表示已过期）
        """
        now = datetime.now(timezone.utc)
        delta = expiry_date - now
        return delta.days
    
    def is_expiring_soon(self, cert_info: CertificateInfo) -> bool:
        """
        判断证书是否即将过期（在警告期内）
        
        Args:
            cert_info: 证书信息
            
        Returns:
            bool: 是否即将过期
        """
        return 0 <= cert_info.days_until_expiry <= self.warning_days
    
    def is_expired(self, cert_info: CertificateInfo) -> bool:
        """
        判断证书是否已过期
        
        Args:
            cert_info: 证书信息
            
        Returns:
            bool: 是否已过期
        """
        return cert_info.days_until_expiry < 0
    
    def filter_expiring_certificates(self, certificates: List[CertificateInfo]) -> List[CertificateInfo]:
        """
        筛选即将过期的证书
        
        Args:
            certificates: 证书列表
            
        Returns:
            List[CertificateInfo]: 即将过期的证书列表
        """
        return [cert for cert in certificates if self.is_expiring_soon(cert)]
    
    def filter_expired_certificates(self, certificates: List[CertificateInfo]) -> List[CertificateInfo]:
        """
        筛选已过期的证书
        
        Args:
            certificates: 证书列表
            
        Returns:
            List[CertificateInfo]: 已过期的证书列表
        """
        return [cert for cert in certificates if self.is_expired(cert)]
    
    def categorize_certificates(self, certificates: List[CertificateInfo]) -> dict:
        """
        对证书进行分类
        
        Args:
            certificates: 证书列表
            
        Returns:
            dict: 分类结果
        """
        valid_certs = [cert for cert in certificates if cert.is_valid]
        
        return {
            'total': len(certificates),
            'valid': len(valid_certs),
            'invalid': len(certificates) - len(valid_certs),
            'expired': self.filter_expired_certificates(valid_certs),
            'expiring_soon': self.filter_expiring_certificates(valid_certs),
            'healthy': [cert for cert in valid_certs 
                       if not self.is_expired(cert) and not self.is_expiring_soon(cert)]
        }
    
    def get_expiry_summary(self, certificates: List[CertificateInfo]) -> str:
        """
        获取过期状态摘要
        
        Args:
            certificates: 证书列表
            
        Returns:
            str: 摘要信息
        """
        categorized = self.categorize_certificates(certificates)
        
        summary_parts = [
            f"总计: {categorized['total']} 个域名",
            f"有效: {categorized['valid']} 个",
            f"无效: {categorized['invalid']} 个"
        ]
        
        if categorized['expired']:
            summary_parts.append(f"已过期: {len(categorized['expired'])} 个")
        
        if categorized['expiring_soon']:
            summary_parts.append(f"即将过期({self.warning_days}天内): {len(categorized['expiring_soon'])} 个")
        
        if categorized['healthy']:
            summary_parts.append(f"健康: {len(categorized['healthy'])} 个")
        
        return ", ".join(summary_parts)