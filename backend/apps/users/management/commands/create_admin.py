from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    help = '创建默认管理员用户'

    def handle(self, *args, **options):
        username = 'admin'
        password = 'admin123'
        email = 'admin@example.com'

        # 检查用户是否已存在
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'用户 {username} 已存在')
            )
            user = User.objects.get(username=username)
            # 确保有 token
            token, created = Token.objects.get_or_create(user=user)
            if not created:
                self.stdout.write(f'Token: {token.key}')
            else:
                self.stdout.write(self.style.SUCCESS(f'Token: {token.key}'))
            return

        # 创建管理员用户
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )

        # 创建 token
        token = Token.objects.create(user=user)

        self.stdout.write(
            self.style.SUCCESS(
                f'成功创建管理员用户:\n'
                f'用户名: {username}\n'
                f'密码: {password}\n'
                f'Email: {email}\n'
                f'Token: {token.key}'
            )
        )
