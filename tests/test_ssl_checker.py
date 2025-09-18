"""
SSL证书检查器测试
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import ssl
import socket

from ssl_certificate_monitor.services.ssl_checker import SSLCertificateChecker
from ssl_certificate_monitor.models import CertificateInfo


class TestSSLCertificateChecker:
    """SSL证书检查器测试类"""
    
    def setup_method(self):
        """测试前准备"""
        self.checker = SSLCertificateChecker(timeout=5)
    
    def test_clean_domain(self):
        """测试域名清理功能"""
        # 测试各种域名格式
        assert self.checker._clean_domain("https://example.com") == "example.com"
        assert self.checker._clean_domain("http://example.com") == "example.com"
        assert self.checker._clean_domain("example.com:443") == "example.com"
        assert self.checker._clean_domain("example.com/path") == "example.com"
        assert self.checker._clean_domain("  EXAMPLE.COM  ") == "example.com"
        assert self.checker._clean_domain("https://example.com:443/path") == "example.com"
    
    def test_parse_expiry_date(self):
        """测试证书过期时间解析"""
        cert = {
            'notAfter': 'Dec 31 23:59:59 2024 GMT'
        }
        
        expiry_date = self.checker._parse_expiry_date(cert)
        
        assert expiry_date.year == 2024
        assert expiry_date.month == 12
        assert expiry_date.day == 31
        assert expiry_date.tzinfo == timezone.utc
    
    def test_parse_expiry_date_missing(self):
        """测试缺少过期时间的证书"""
        cert = {}
        
        with pytest.raises(Exception, match="证书中未找到过期时间信息"):
            self.checker._parse_expiry_date(cert)
    
    def test_parse_issuer_organization(self):
        """测试解析证书颁发者（组织名称）"""
        cert = {
            'issuer': [
                [['countryName', 'US']],
                [['organizationName', 'Let\'s Encrypt']],
                [['commonName', 'R3']]
            ]
        }
        
        issuer = self.checker._parse_issuer(cert)
        assert issuer == "Let's Encrypt"
    
    def test_parse_issuer_common_name(self):
        """测试解析证书颁发者（通用名称）"""
        cert = {
            'issuer': [
                [['countryName', 'US']],
                [['commonName', 'Test CA']]
            ]
        }
        
        issuer = self.checker._parse_issuer(cert)
        assert issuer == "Test CA"
    
    def test_parse_issuer_unknown(self):
        """测试未知颁发者"""
        cert = {
            'issuer': [
                [['countryName', 'US']]
            ]
        }
        
        issuer = self.checker._parse_issuer(cert)
        assert issuer == "Unknown Issuer"
    
    def test_calculate_days_until_expiry_future(self):
        """测试计算未来过期时间"""
        from datetime import timedelta
        
        # 创建一个未来30天的时间
        future_date = datetime.now(timezone.utc) + timedelta(days=30)
        
        days = self.checker._calculate_days_until_expiry(future_date)
        assert days >= 29  # 考虑到时间差异，允许29-30天
    
    def test_calculate_days_until_expiry_past(self):
        """测试计算过去过期时间"""
        # 创建一个过去的时间
        past_date = datetime.now(timezone.utc).replace(
            year=datetime.now(timezone.utc).year - 1
        )
        
        days = self.checker._calculate_days_until_expiry(past_date)
        assert days < 0
    
    @patch('ssl_certificate_monitor.services.ssl_checker.socket.create_connection')
    @patch('ssl_certificate_monitor.services.ssl_checker.ssl.create_default_context')
    def test_get_ssl_certificate_success(self, mock_context, mock_connection):
        """测试成功获取SSL证书"""
        # 模拟SSL证书
        mock_cert = {
            'notAfter': 'Dec 31 23:59:59 2024 GMT',
            'issuer': [[['organizationName', 'Test CA']]]
        }
        
        # 设置模拟对象
        mock_sock = MagicMock()
        mock_connection.return_value.__enter__.return_value = mock_sock
        
        mock_ssl_sock = MagicMock()
        mock_ssl_sock.getpeercert.return_value = mock_cert
        mock_context.return_value.wrap_socket.return_value.__enter__.return_value = mock_ssl_sock
        
        # 执行测试
        cert = self.checker._get_ssl_certificate("example.com")
        
        # 验证结果
        assert cert == mock_cert
        mock_connection.assert_called_once_with(("example.com", 443), timeout=5)
    
    @patch('ssl_certificate_monitor.services.ssl_checker.socket.create_connection')
    def test_get_ssl_certificate_connection_error(self, mock_connection):
        """测试连接错误"""
        mock_connection.side_effect = socket.timeout("Connection timeout")
        
        with pytest.raises(socket.timeout):
            self.checker._get_ssl_certificate("nonexistent.com")
    
    @patch.object(SSLCertificateChecker, '_get_ssl_certificate')
    def test_check_certificate_success(self, mock_get_cert):
        """测试成功检查证书"""
        # 模拟证书数据
        mock_cert = {
            'notAfter': 'Dec 31 23:59:59 2024 GMT',
            'issuer': [[['organizationName', 'Test CA']]]
        }
        mock_get_cert.return_value = mock_cert
        
        # 执行检查
        result = self.checker.check_certificate("https://example.com")
        
        # 验证结果
        assert isinstance(result, CertificateInfo)
        assert result.domain == "example.com"
        assert result.is_valid is True
        assert result.issuer == "Test CA"
        assert result.error_message is None
    
    @patch.object(SSLCertificateChecker, '_get_ssl_certificate')
    def test_check_certificate_error(self, mock_get_cert):
        """测试检查证书时发生错误"""
        mock_get_cert.side_effect = Exception("Connection failed")
        
        # 执行检查
        result = self.checker.check_certificate("invalid.com")
        
        # 验证结果
        assert isinstance(result, CertificateInfo)
        assert result.domain == "invalid.com"
        assert result.is_valid is False
        assert "Connection failed" in result.error_message