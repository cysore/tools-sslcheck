"""
证书过期计算器测试
"""
import pytest
from datetime import datetime, timezone, timedelta

from ssl_certificate_monitor.services.expiry_calculator import ExpiryCalculator
from ssl_certificate_monitor.models import CertificateInfo


class TestExpiryCalculator:
    """证书过期计算器测试类"""
    
    def setup_method(self):
        """测试前准备"""
        self.calculator = ExpiryCalculator(warning_days=30)
    
    def test_calculate_days_until_expiry_future(self):
        """测试计算未来过期时间"""
        future_date = datetime.now(timezone.utc) + timedelta(days=15)
        days = self.calculator.calculate_days_until_expiry(future_date)
        assert days >= 14  # 考虑到时间差异
    
    def test_calculate_days_until_expiry_past(self):
        """测试计算过去过期时间"""
        past_date = datetime.now(timezone.utc) - timedelta(days=5)
        days = self.calculator.calculate_days_until_expiry(past_date)
        assert days <= -4  # 考虑到时间差异
    
    def test_is_expiring_soon_true(self):
        """测试即将过期判断 - 真"""
        cert_info = CertificateInfo(
            domain="example.com",
            expiry_date=datetime.now(timezone.utc) + timedelta(days=15),
            days_until_expiry=15,
            issuer="Test CA",
            is_valid=True
        )
        
        assert self.calculator.is_expiring_soon(cert_info) is True
    
    def test_is_expiring_soon_false_too_far(self):
        """测试即将过期判断 - 假（时间太远）"""
        cert_info = CertificateInfo(
            domain="example.com",
            expiry_date=datetime.now(timezone.utc) + timedelta(days=60),
            days_until_expiry=60,
            issuer="Test CA",
            is_valid=True
        )
        
        assert self.calculator.is_expiring_soon(cert_info) is False
    
    def test_is_expiring_soon_false_expired(self):
        """测试即将过期判断 - 假（已过期）"""
        cert_info = CertificateInfo(
            domain="example.com",
            expiry_date=datetime.now(timezone.utc) - timedelta(days=5),
            days_until_expiry=-5,
            issuer="Test CA",
            is_valid=True
        )
        
        assert self.calculator.is_expiring_soon(cert_info) is False
    
    def test_is_expired_true(self):
        """测试已过期判断 - 真"""
        cert_info = CertificateInfo(
            domain="example.com",
            expiry_date=datetime.now(timezone.utc) - timedelta(days=5),
            days_until_expiry=-5,
            issuer="Test CA",
            is_valid=True
        )
        
        assert self.calculator.is_expired(cert_info) is True
    
    def test_is_expired_false(self):
        """测试已过期判断 - 假"""
        cert_info = CertificateInfo(
            domain="example.com",
            expiry_date=datetime.now(timezone.utc) + timedelta(days=15),
            days_until_expiry=15,
            issuer="Test CA",
            is_valid=True
        )
        
        assert self.calculator.is_expired(cert_info) is False
    
    def test_filter_expiring_certificates(self):
        """测试筛选即将过期的证书"""
        certificates = [
            CertificateInfo(
                domain="expiring.com",
                expiry_date=datetime.now(timezone.utc) + timedelta(days=15),
                days_until_expiry=15,
                issuer="Test CA",
                is_valid=True
            ),
            CertificateInfo(
                domain="healthy.com",
                expiry_date=datetime.now(timezone.utc) + timedelta(days=60),
                days_until_expiry=60,
                issuer="Test CA",
                is_valid=True
            ),
            CertificateInfo(
                domain="expired.com",
                expiry_date=datetime.now(timezone.utc) - timedelta(days=5),
                days_until_expiry=-5,
                issuer="Test CA",
                is_valid=True
            )
        ]
        
        expiring = self.calculator.filter_expiring_certificates(certificates)
        
        assert len(expiring) == 1
        assert expiring[0].domain == "expiring.com"
    
    def test_filter_expired_certificates(self):
        """测试筛选已过期的证书"""
        certificates = [
            CertificateInfo(
                domain="expiring.com",
                expiry_date=datetime.now(timezone.utc) + timedelta(days=15),
                days_until_expiry=15,
                issuer="Test CA",
                is_valid=True
            ),
            CertificateInfo(
                domain="expired.com",
                expiry_date=datetime.now(timezone.utc) - timedelta(days=5),
                days_until_expiry=-5,
                issuer="Test CA",
                is_valid=True
            )
        ]
        
        expired = self.calculator.filter_expired_certificates(certificates)
        
        assert len(expired) == 1
        assert expired[0].domain == "expired.com"
    
    def test_categorize_certificates(self):
        """测试证书分类"""
        certificates = [
            CertificateInfo(
                domain="expiring.com",
                expiry_date=datetime.now(timezone.utc) + timedelta(days=15),
                days_until_expiry=15,
                issuer="Test CA",
                is_valid=True
            ),
            CertificateInfo(
                domain="healthy.com",
                expiry_date=datetime.now(timezone.utc) + timedelta(days=60),
                days_until_expiry=60,
                issuer="Test CA",
                is_valid=True
            ),
            CertificateInfo(
                domain="expired.com",
                expiry_date=datetime.now(timezone.utc) - timedelta(days=5),
                days_until_expiry=-5,
                issuer="Test CA",
                is_valid=True
            ),
            CertificateInfo(
                domain="invalid.com",
                expiry_date=datetime.now(timezone.utc),
                days_until_expiry=-1,
                issuer="Unknown",
                is_valid=False,
                error_message="Connection failed"
            )
        ]
        
        result = self.calculator.categorize_certificates(certificates)
        
        assert result['total'] == 4
        assert result['valid'] == 3
        assert result['invalid'] == 1
        assert len(result['expired']) == 1
        assert len(result['expiring_soon']) == 1
        assert len(result['healthy']) == 1
        
        assert result['expired'][0].domain == "expired.com"
        assert result['expiring_soon'][0].domain == "expiring.com"
        assert result['healthy'][0].domain == "healthy.com"
    
    def test_get_expiry_summary(self):
        """测试获取过期状态摘要"""
        certificates = [
            CertificateInfo(
                domain="expiring.com",
                expiry_date=datetime.now(timezone.utc) + timedelta(days=15),
                days_until_expiry=15,
                issuer="Test CA",
                is_valid=True
            ),
            CertificateInfo(
                domain="expired.com",
                expiry_date=datetime.now(timezone.utc) - timedelta(days=5),
                days_until_expiry=-5,
                issuer="Test CA",
                is_valid=True
            )
        ]
        
        summary = self.calculator.get_expiry_summary(certificates)
        
        assert "总计: 2 个域名" in summary
        assert "有效: 2 个" in summary
        assert "无效: 0 个" in summary
        assert "已过期: 1 个" in summary
        assert "即将过期(30天内): 1 个" in summary
    
    def test_custom_warning_days(self):
        """测试自定义警告天数"""
        calculator = ExpiryCalculator(warning_days=7)
        
        cert_info = CertificateInfo(
            domain="example.com",
            expiry_date=datetime.now(timezone.utc) + timedelta(days=15),
            days_until_expiry=15,
            issuer="Test CA",
            is_valid=True
        )
        
        # 15天对于7天警告期来说不算即将过期
        assert calculator.is_expiring_soon(cert_info) is False
        
        # 但对于30天警告期来说算即将过期
        assert self.calculator.is_expiring_soon(cert_info) is True