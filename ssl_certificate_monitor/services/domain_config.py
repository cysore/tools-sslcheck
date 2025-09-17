"""
域名配置管理服务
"""
import os
import re
from typing import List
import logging

from ..interfaces import DomainConfigManagerInterface


class DomainConfigManager(DomainConfigManagerInterface):
    """域名配置管理器实现"""
    
    def __init__(self, env_var_name: str = "DOMAINS"):
        """
        初始化域名配置管理器
        
        Args:
            env_var_name: 环境变量名称，默认为"DOMAINS"
        """
        self.env_var_name = env_var_name
        self.logger = logging.getLogger(__name__)
        
        # 域名格式验证正则表达式
        self.domain_pattern = re.compile(
            r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        )
        
        # 默认域名列表（作为备选）
        self.default_domains = []
    
    def get_domains(self) -> List[str]:
        """
        从环境变量获取域名列表（逗号分隔）
        
        Returns:
            List[str]: 域名列表
        """
        try:
            # 从环境变量读取域名列表
            domains_str = os.getenv(self.env_var_name, "")
            
            if not domains_str.strip():
                self.logger.warning(f"环境变量 {self.env_var_name} 为空，使用默认域名列表")
                return self.default_domains.copy()
            
            # 解析域名列表
            raw_domains = [domain.strip() for domain in domains_str.split(',')]
            
            # 清理和验证域名
            valid_domains = []
            for domain in raw_domains:
                if domain:  # 跳过空字符串
                    cleaned_domain = self._clean_domain(domain)
                    if self.validate_domain(cleaned_domain):
                        valid_domains.append(cleaned_domain)
                    else:
                        self.logger.warning(f"跳过无效域名: {domain}")
            
            if not valid_domains:
                self.logger.warning("没有找到有效的域名，使用默认域名列表")
                return self.default_domains.copy()
            
            self.logger.info(f"成功加载 {len(valid_domains)} 个域名")
            return valid_domains
            
        except Exception as e:
            self.logger.error(f"读取域名配置时发生错误: {str(e)}")
            return self.default_domains.copy()
    
    def validate_domain(self, domain: str) -> bool:
        """
        验证域名格式
        
        Args:
            domain: 要验证的域名
            
        Returns:
            bool: 域名是否有效
        """
        if not domain or not isinstance(domain, str):
            return False
        
        # 检查长度
        if len(domain) > 253:
            return False
        
        # 检查是否包含无效字符
        if domain.startswith('.') or domain.endswith('.'):
            return False
        
        # 使用正则表达式验证格式
        return bool(self.domain_pattern.match(domain))
    
    def _clean_domain(self, domain: str) -> str:
        """
        清理域名格式
        
        Args:
            domain: 原始域名
            
        Returns:
            str: 清理后的域名
        """
        if not domain:
            return ""
        
        # 移除协议前缀
        if domain.startswith('https://'):
            domain = domain[8:]
        elif domain.startswith('http://'):
            domain = domain[7:]
        
        # 移除www前缀（可选）
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # 移除路径部分
        if '/' in domain:
            domain = domain.split('/')[0]
        
        # 移除端口号
        if ':' in domain:
            domain = domain.split(':')[0]
        
        # 转换为小写并去除空格
        return domain.strip().lower()
    
    def set_default_domains(self, domains: List[str]) -> None:
        """
        设置默认域名列表
        
        Args:
            domains: 默认域名列表
        """
        valid_defaults = []
        for domain in domains:
            cleaned = self._clean_domain(domain)
            if self.validate_domain(cleaned):
                valid_defaults.append(cleaned)
            else:
                self.logger.warning(f"跳过无效的默认域名: {domain}")
        
        self.default_domains = valid_defaults
        self.logger.info(f"设置了 {len(valid_defaults)} 个默认域名")
    
    def get_domain_count(self) -> int:
        """
        获取配置的域名数量
        
        Returns:
            int: 域名数量
        """
        return len(self.get_domains())
    
    def validate_configuration(self) -> dict:
        """
        验证配置状态
        
        Returns:
            dict: 配置验证结果
        """
        domains = self.get_domains()
        env_value = os.getenv(self.env_var_name, "")
        
        return {
            'env_var_name': self.env_var_name,
            'env_var_exists': bool(env_value),
            'env_var_value': env_value,
            'total_domains': len(domains),
            'valid_domains': domains,
            'using_defaults': len(domains) == len(self.default_domains) and domains == self.default_domains,
            'has_defaults': len(self.default_domains) > 0
        }