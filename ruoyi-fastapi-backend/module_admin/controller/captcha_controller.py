import uuid
from datetime import timedelta

from fastapi import Request, Response

from common.annotation.rate_limit_annotation import ApiRateLimit, ApiRateLimitPreset
from common.constant import ApiNamespace
from common.enums import RedisInitKeyConfig
from common.router import APIRouterPro
from common.vo import DynamicResponseModel
from module_admin.entity.vo.login_vo import CaptchaCode
from module_admin.service.captcha_service import CaptchaService
from utils.log_util import logger
from utils.response_util import ResponseUtil

captcha_controller = APIRouterPro(order_num=2, tags=['验证码模块'])


def _redis_flag_enabled(raw: str | bytes | None, *, default: bool = True) -> bool:
    """解析 redis 中的开关配置。缺省/空值按 default；兼容 true/1/yes/on。"""
    if raw is None:
        return default
    text = raw.decode() if isinstance(raw, (bytes, bytearray)) else str(raw)
    text = text.strip().lower()
    if text == '':
        return default
    if text in {'true', '1', 'yes', 'y', 'on'}:
        return True
    if text in {'false', '0', 'no', 'n', 'off'}:
        return False
    return default


@captcha_controller.get(
    '/captchaImage',
    summary='获取图片验证码接口',
    description='用于获取图片验证码',
    response_model=DynamicResponseModel[CaptchaCode],
)
@ApiRateLimit(namespace=ApiNamespace.CAPTCHA_IMAGE, preset=ApiRateLimitPreset.ANON_AUTH_CAPTCHA)
async def get_captcha_image(request: Request) -> Response:
    captcha_raw = await request.app.state.redis.get(
        f'{RedisInitKeyConfig.SYS_CONFIG.key}:sys.account.captchaEnabled'
    )
    # 验证码默认开启：避免测试改 redis 后误关导致登录页不显示验证码
    captcha_enabled = _redis_flag_enabled(captcha_raw, default=True)
    register_raw = await request.app.state.redis.get(
        f'{RedisInitKeyConfig.SYS_CONFIG.key}:sys.account.registerUser'
    )
    register_enabled = _redis_flag_enabled(register_raw, default=False)
    session_id = str(uuid.uuid4())
    captcha_result = await CaptchaService.create_captcha_image_service()
    image = captcha_result[0]
    computed_result = captcha_result[1]
    await request.app.state.redis.set(
        f'{RedisInitKeyConfig.CAPTCHA_CODES.key}:{session_id}', computed_result, ex=timedelta(minutes=2)
    )
    logger.info(f'编号为{session_id}的会话获取图片验证码成功 captchaEnabled={captcha_enabled}')

    return ResponseUtil.success(
        model_content=CaptchaCode(
            captchaEnabled=captcha_enabled, registerEnabled=register_enabled, img=image, uuid=session_id
        )
    )
