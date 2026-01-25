# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
import base64
from datetime import timedelta
from odoo import fields


class TestPKICertificate(TransactionCase):
    """Unit tests cho PKI Certificate"""
    
    def setUp(self):
        super(TestPKICertificate, self).setUp()
        
        # Setup test user
        self.test_user = self.env['res.users'].create({
            'name': 'Test User PKI',
            'login': 'test_pki@example.com',
            'email': 'test_pki@example.com',
        })
        
        # Setup test certificate
        self.test_cert = self.env['pki.certificate'].create({
            'name': 'Test Certificate',
            'user_id': self.test_user.id,
            'subject_common_name': 'Test User',
            'subject_organization': 'Test Org',
            'subject_email': 'test@example.com',
            'key_size': 2048,
            'hash_algorithm': 'SHA256',
            'valid_from': fields.Datetime.now(),
            'valid_to': fields.Datetime.now() + timedelta(days=365),
        })
    
    def test_01_certificate_creation(self):
        """Test tạo certificate"""
        self.assertTrue(self.test_cert.id)
        self.assertEqual(self.test_cert.state, 'draft')
        self.assertEqual(self.test_cert.key_size, 2048)
        self.assertEqual(self.test_cert.hash_algorithm, 'SHA256')
    
    def test_02_generate_keypair(self):
        """Test sinh keypair"""
        self.test_cert.action_generate_keypair()
        
        # Check keys đã được sinh
        self.assertTrue(self.test_cert.private_key)
        self.assertTrue(self.test_cert.public_key)
        self.assertTrue(self.test_cert.certificate)
        self.assertEqual(self.test_cert.state, 'active')
    
    def test_03_certificate_validity(self):
        """Test kiểm tra validity"""
        self.test_cert.action_generate_keypair()
        
        # Certificate phải valid
        self.test_cert._compute_is_valid()
        self.assertTrue(self.test_cert.is_valid)
        
        # Set expired
        self.test_cert.write({
            'valid_to': fields.Datetime.now() - timedelta(days=1)
        })
        self.test_cert._compute_is_valid()
        self.assertFalse(self.test_cert.is_valid)
    
    def test_04_key_size_validation(self):
        """Test validation key size"""
        with self.assertRaises(ValidationError):
            self.env['pki.certificate'].create({
                'name': 'Invalid Cert',
                'user_id': self.test_user.id,
                'key_size': 1024,  # Invalid size
            })
    
    def test_05_get_private_key(self):
        """Test lấy private key object"""
        self.test_cert.action_generate_keypair()
        
        # Get private key
        private_key_obj = self.test_cert.get_private_key_object()
        self.assertIsNotNone(private_key_obj)
    
    def test_06_get_public_key(self):
        """Test lấy public key object"""
        self.test_cert.action_generate_keypair()
        
        # Get public key
        public_key_obj = self.test_cert.get_public_key_object()
        self.assertIsNotNone(public_key_obj)
    
    def test_07_certificate_revocation(self):
        """Test thu hồi certificate"""
        self.test_cert.action_generate_keypair()
        
        # Revoke
        self.test_cert.action_revoke('key_compromise', 'Test revocation')
        
        # Check state
        self.assertEqual(self.test_cert.state, 'revoked')
        self.assertTrue(self.test_cert.is_revoked)
        
        # Check CRL entry được tạo
        crl_entry = self.env['pki.certificate.revocation'].search([
            ('certificate_id', '=', self.test_cert.id)
        ])
        self.assertTrue(crl_entry)
        self.assertEqual(crl_entry.reason_code, 'key_compromise')


class TestWizardKyDienTu(TransactionCase):
    """Unit tests cho Wizard Ký điện tử"""
    
    def setUp(self):
        super(TestWizardKyDienTu, self).setUp()
        
        # Setup test data
        self.test_user = self.env['res.users'].create({
            'name': 'Test Signer',
            'login': 'signer@example.com',
            'email': 'signer@example.com',
        })
        
        self.test_nhan_vien = self.env['nhan_vien'].create({
            'ten_nv': 'Test Signer',
            'user_id': self.test_user.id,
            'chuc_vu': 'Tester',
        })
        
        self.test_loai_vb = self.env['loai_van_ban'].create({
            'ten_loai': 'Hợp đồng test',
            'ma_loai': 'HD_TEST',
        })
        
        # Create test PDF file (dummy)
        dummy_pdf = b'%PDF-1.4 Test PDF content'
        
        self.test_van_ban = self.env['van_ban'].create({
            'ten_van_ban': 'Test Document',
            'loai_van_ban_id': self.test_loai_vb.id,
            'nguoi_tao_id': self.test_nhan_vien.id,
            'file_dinh_kem': base64.b64encode(dummy_pdf),
            'ten_file': 'test.pdf',
        })
        
        # Create dummy signature image
        dummy_image = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        self.dummy_signature = base64.b64encode(dummy_image)
    
    def test_01_wizard_creation(self):
        """Test tạo wizard"""
        wizard = self.env['wizard.ky.dien.tu'].create({
            'van_ban_id': self.test_van_ban.id,
            'nguoi_ky_id': self.test_nhan_vien.id,
            'chu_ky': self.dummy_signature,
            'ho_ten_xac_nhan': 'Test Signer',
            'xac_nhan': True,
        })
        
        self.assertTrue(wizard.id)
        self.assertEqual(wizard.van_ban_id.id, self.test_van_ban.id)
    
    def test_02_generate_keys_from_image(self):
        """Test tự động sinh keys từ ảnh"""
        wizard = self.env['wizard.ky.dien.tu'].create({
            'van_ban_id': self.test_van_ban.id,
            'nguoi_ky_id': self.test_nhan_vien.id,
            'chu_ky': self.dummy_signature,
            'ho_ten_xac_nhan': 'Test Signer',
            'xac_nhan': True,
        })
        
        # Keys should be auto-generated
        self.assertTrue(wizard.keys_generated)
        self.assertTrue(wizard.private_key_generated)
        self.assertTrue(wizard.public_key_generated)
    
    def test_03_signature_validation(self):
        """Test validation khi ký"""
        wizard = self.env['wizard.ky.dien.tu'].create({
            'van_ban_id': self.test_van_ban.id,
            'nguoi_ky_id': self.test_nhan_vien.id,
            'chu_ky': self.dummy_signature,
            'xac_nhan': False,  # Chưa xác nhận
        })
        
        # Should raise error vì chưa xác nhận
        with self.assertRaises(UserError):
            wizard.action_ky()
    
    def test_04_signature_name_verification(self):
        """Test xác thực họ tên"""
        wizard = self.env['wizard.ky.dien.tu'].create({
            'van_ban_id': self.test_van_ban.id,
            'nguoi_ky_id': self.test_nhan_vien.id,
            'chu_ky': self.dummy_signature,
            'ho_ten_xac_nhan': 'Wrong Name',  # Sai tên
            'xac_nhan': True,
        })
        
        # Should raise error vì tên không khớp
        with self.assertRaises(UserError):
            wizard.action_ky()


class TestVanBanSignatureLog(TransactionCase):
    """Unit tests cho Signature Log"""
    
    def setUp(self):
        super(TestVanBanSignatureLog, self).setUp()
        
        # Setup test data
        self.test_user = self.env['res.users'].create({
            'name': 'Test User',
            'login': 'testlog@example.com',
        })
        
        self.test_cert = self.env['pki.certificate'].create({
            'name': 'Test Cert',
            'user_id': self.test_user.id,
            'key_size': 2048,
            'hash_algorithm': 'SHA256',
        })
        
        self.test_van_ban = self.env['van_ban'].create({
            'ten_van_ban': 'Test Doc',
            'loai_van_ban_id': self.env['loai_van_ban'].create({
                'ten_loai': 'Test Type',
                'ma_loai': 'TEST',
            }).id,
        })
    
    def test_01_signature_log_creation(self):
        """Test tạo signature log"""
        log = self.env['van_ban.signature.log'].create({
            'van_ban_id': self.test_van_ban.id,
            'user_id': self.test_user.id,
            'certificate_id': self.test_cert.id,
            'is_valid': True,
            'file_sha256': 'test_hash_12345',
            'digital_signature': 'test_signature',
        })
        
        self.assertTrue(log.id)
        self.assertEqual(log.verification_status, 'signed')
    
    def test_02_one_target_constraint(self):
        """Test constraint: chỉ 1 văn bản"""
        with self.assertRaises(ValidationError):
            self.env['van_ban.signature.log'].create({
                'van_ban_id': self.test_van_ban.id,
                'van_ban_di_id': self.test_van_ban.id,  # Không được 2 targets
                'user_id': self.test_user.id,
            })


class TestCertificateRevocation(TransactionCase):
    """Unit tests cho CRL"""
    
    def setUp(self):
        super(TestCertificateRevocation, self).setUp()
        
        self.test_user = self.env['res.users'].create({
            'name': 'Test User CRL',
            'login': 'crl@example.com',
        })
        
        self.test_cert = self.env['pki.certificate'].create({
            'name': 'Test Cert for CRL',
            'user_id': self.test_user.id,
            'state': 'active',
        })
    
    def test_01_crl_creation(self):
        """Test tạo CRL entry"""
        crl = self.env['pki.certificate.revocation'].create({
            'certificate_id': self.test_cert.id,
            'reason_code': 'key_compromise',
            'reason_description': 'Test revocation',
        })
        
        self.assertTrue(crl.id)
        self.assertEqual(crl.state, 'active')
        
        # Check certificate state changed
        self.assertEqual(self.test_cert.state, 'revoked')
    
    def test_02_check_revoked(self):
        """Test kiểm tra certificate bị revoke"""
        # Create revocation
        self.env['pki.certificate.revocation'].create({
            'certificate_id': self.test_cert.id,
            'reason_code': 'superseded',
        })
        
        # Check
        is_revoked, reason = self.env['pki.certificate.revocation'].check_certificate_revoked(
            self.test_cert.id
        )
        
        self.assertTrue(is_revoked)
        self.assertIn('superseded', reason.lower())
    
    def test_03_reactivate_certificate(self):
        """Test reactivate certificate"""
        # Revoke with 'hold' reason
        crl = self.env['pki.certificate.revocation'].create({
            'certificate_id': self.test_cert.id,
            'reason_code': 'certificate_hold',
        })
        
        # Reactivate
        crl.action_remove_from_crl()
        
        self.assertEqual(crl.state, 'removed')
        self.assertEqual(self.test_cert.state, 'active')


class TestCertificateRotation(TransactionCase):
    """Unit tests cho Certificate Rotation"""
    
    def setUp(self):
        super(TestCertificateRotation, self).setUp()
        
        self.test_user = self.env['res.users'].create({
            'name': 'Test User Rotation',
            'login': 'rotation@example.com',
            'email': 'rotation@example.com',
        })
        
        self.test_cert = self.env['pki.certificate'].create({
            'name': 'Test Cert Rotation',
            'user_id': self.test_user.id,
            'subject_common_name': 'Test',
            'key_size': 2048,
            'state': 'draft',
        })
        
        # Generate keypair
        self.test_cert.action_generate_keypair()
    
    def test_01_rotation_creation(self):
        """Test tạo rotation"""
        rotation = self.env['pki.certificate.rotation'].create({
            'old_certificate_id': self.test_cert.id,
            'rotation_type': 'manual',
            'rotation_reason': 'Test rotation',
        })
        
        self.assertTrue(rotation.id)
        self.assertEqual(rotation.state, 'pending')
    
    def test_02_execute_rotation(self):
        """Test thực hiện rotation"""
        rotation = self.env['pki.certificate.rotation'].create({
            'old_certificate_id': self.test_cert.id,
            'rotation_type': 'manual',
        })
        
        # Execute
        rotation.action_execute_rotation()
        
        # Check
        self.assertEqual(rotation.state, 'completed')
        self.assertTrue(rotation.new_certificate_id)
        self.assertEqual(self.test_cert.state, 'revoked')
    
    def test_03_check_expiring_certs(self):
        """Test cron check expiring certificates"""
        # Set certificate to expire soon
        self.test_cert.write({
            'valid_to': fields.Datetime.now() + timedelta(days=20)
        })
        
        # Run cron
        count = self.env['pki.certificate.rotation'].cron_check_expiring_certificates()
        
        # Should create rotation
        self.assertGreater(count, 0)
