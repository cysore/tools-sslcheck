"""
SSL证书检查服务
"""
import ssl
import socket
from datetime import datetime, timezone
from typing import Optional
import logging

from ..interfaces import SSLCertificateCheckerInterface
from ..models import CertificateInfo
from .error_handler import NetworkErrorHandler


class SSLCertificateChecker(SSLCertificateCheckerInterface):
    """SSL证书检查器实现"""
    
    def __init__(self, timeout: int = 10, port: int = 443):
        """
        初始化SSL证书检查器
        
        Args:
            timeout: 连接超时时间（秒）
            port: SSL端口，默认443
        """
        self.timeout = timeout
        self.port = port
        self.logger = logging.getLogger(__name__)
        self.error_handler = NetworkErrorHandler(max_retries=3, base_delay=1.0)
    
    def check_certificate(self, domain: str) -> CertificateInfo:
        """
        检查单个域名的SSL证书
        
        Args:
            domain: 要检查的域名
            
        Returns:
            CertificateInfo: 证书信息
        """
        try:
            # 清理域名（移除协议前缀等）
            clean_domain = self._clean_domain(domain)
            
            # 使用错误处理器重试获取SSL证书
            cert = self.error_handler.with_retry(self._get_ssl_certificate, clean_domain)
            
            # 解析证书信息
            expiry_date = self._parse_expiry_date(cert)
            issuer = self._parse_issuer(cert)
            
            # 计算剩余天数
            days_until_expiry = self._calculate_days_until_expiry(expiry_date)
            
            return CertificateInfo(
                domain=clean_domain,
                expiry_date=expiry_date,
                days_until_expiry=days_until_expiry,
                issuer=issuer,
                is_valid=True
            )
            
        except Exception as e:
            # 使用错误处理器处理SSL连接错误
            error_info = self.error_handler.handle_ssl_connection_error(domain, e)
            
            self.logger.error(f"检查域名 {domain} 的证书时发生错误: {str(e)}")
            
            return CertificateInfo(
                domain=domain,
                expiry_date=datetime.now(timezone.utc),
                days_until_expiry=-1,
                issuer="Unknown",
                is_valid=False,
                error_message=f"{error_info['error_type']}: {error_info['error_message']}"
            )
    
    def _clean_domain(self, domain: str) -> str:
        """
        清理域名格式
        
        Args:
            domain: 原始域名
            
        Returns:
            str: 清理后的域名
        """
        # 移除协议前缀
        if domain.startswith('https://'):
            domain = domain[8:]
        elif domain.startswith('http://'):
            domain = domain[7:]
        
        # 移除路径部分
        if '/' in domain:
            domain = domain.split('/')[0]
        
        # 移除端口号
        if ':' in domain:
            domain = domain.split(':')[0]
        
        return domain.strip().lower()
    
    def _get_ssl_certificate(self, domain: str) -> dict:
        """
        获取SSL证书
        
        Args:
            domain: 域名
            
        Returns:
            dict: SSL证书信息
            
        Raises:
            Exception: 连接失败或证书获取失败
        """
        context = ssl.create_default_context()
        
        with socket.create_connection((domain, self.port), timeout=self.timeout) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                
        if not cert:
            raise Exception(f"无法获取域名 {domain} 的SSL证书")
        
        return cert
    
    def _parse_expiry_date(self, cert: dict) -> datetime:
        """
        解析证书过期时间
        
        Args:
            cert: SSL证书信息
            
        Returns:
            datetime: 过期时间
        """
        not_after = cert.get('notAfter')
        if not not_after:
            raise Exception("证书中未找到过期时间信息")
        
        # 解析时间格式：'Dec 31 23:59:59 2024 GMT'
        expiry_date = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
        # 转换为UTC时区
        expiry_date = expiry_date.replace(tzinfo=timezone.utc)
        
        return expiry_date
    
    def _parse_issuer(self, cert: dict) -> str:
        """
        解析证书颁发者
        
        Args:
            cert: SSL证书信息
            
        Returns:
            str: 证书颁发者
        """
        issuer = cert.get('issuer', [])
        
        # 查找组织名称
        for item in issuer:
            if item[0][0] == 'organizationName':
                return item[0][1]
        
        # 如果没有找到组织名称，查找通用名称
        for item in issuer:
            if item[0][0] == 'commonName':
                return item[0][1]
        
        return "Unknown Issuer"
    
    def _calculate_days_until_expiry(self, expiry_date: datetime) -> int:
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