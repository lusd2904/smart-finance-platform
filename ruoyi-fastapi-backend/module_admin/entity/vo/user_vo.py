"""
用户管理业务数据模型。

框架级身份模型（TokenData / UserModel / UserInfoModel / CurrentUserModel）
已下沉至 common.entity.vo.user_vo，本模块仅保留管理端 CRUD DTO。
"""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from common.entity.vo.dept_vo import DeptModel
from common.entity.vo.post_vo import PostModel
from common.entity.vo.role_vo import RoleModel
from common.entity.vo.user_vo import UserInfoModel, UserModel
from exceptions.exception import ModelValidatorException


class UserRowModel(UserModel):
    """
    用户列表行数据模型
    """

    dept: DeptModel | None = Field(default=None, description='部门信息')


class UserRoleModel(BaseModel):
    """
    用户和角色关联表对应pydantic模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    user_id: int | None = Field(default=None, description='用户ID')
    role_id: int | None = Field(default=None, description='角色ID')


class UserPostModel(BaseModel):
    """
    用户与岗位关联表对应pydantic模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    user_id: int | None = Field(default=None, description='用户ID')
    post_id: int | None = Field(default=None, description='岗位ID')


class UserDetailModel(BaseModel):
    """
    获取用户详情信息响应模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    data: UserInfoModel | None | None = Field(default=None, description='用户信息')
    post_ids: list | None = Field(default=None, description='岗位ID信息')
    posts: list[PostModel | None] = Field(description='岗位信息')
    role_ids: list | None = Field(default=None, description='角色ID信息')
    roles: list[RoleModel | None] = Field(description='角色信息')


class UserProfileModel(BaseModel):
    """
    获取个人信息响应模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    data: UserInfoModel | None = Field(description='用户信息')
    post_group: str | None = Field(description='岗位信息')
    role_group: str | None = Field(description='角色信息')


class AvatarModel(BaseModel):
    """
    上传头像响应模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    img_url: str = Field(description='头像地址')


class UserQueryModel(UserModel):
    """
    用户管理不分页查询模型
    """

    begin_time: str | None = Field(default=None, description='开始时间')
    end_time: str | None = Field(default=None, description='结束时间')


class UserPageQueryModel(UserQueryModel):
    """
    用户管理分页查询模型
    """

    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class AddUserModel(UserModel):
    """
    新增用户模型
    """

    role_ids: list | None = Field(default=[], description='角色ID信息')
    post_ids: list | None = Field(default=[], description='岗位ID信息')
    type: str | None = Field(default=None, description='操作类型')


class EditUserModel(AddUserModel):
    """
    编辑用户模型
    """

    role: list | None = Field(default=[], description='角色信息')


class ResetPasswordModel(BaseModel):
    """
    重置密码模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    old_password: str | None = Field(default=None, description='旧密码')
    new_password: str | None = Field(default=None, description='新密码')

    @model_validator(mode='after')
    def check_new_password(self) -> 'ResetPasswordModel':
        pattern = r"""^[^<>"'|\\]+$"""
        if self.new_password is None or re.match(pattern, self.new_password):
            return self
        raise ModelValidatorException(message='密码不能包含非法字符：< > " \' \\ |')


class ResetUserModel(UserModel):
    """
    重置用户密码模型
    """

    old_password: str | None = Field(default=None, description='旧密码')
    sms_code: str | None = Field(default=None, description='验证码')
    session_id: str | None = Field(default=None, description='会话id')


class DeleteUserModel(BaseModel):
    """
    删除用户模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    user_ids: str = Field(description='需要删除的用户ID')
    update_by: str | None = Field(default=None, description='更新者')
    update_time: datetime | None = Field(default=None, description='更新时间')


class UserRoleQueryModel(UserModel):
    """
    用户角色关联管理不分页查询模型
    """

    role_id: int | None = Field(default=None, description='角色ID')


class UserRolePageQueryModel(UserRoleQueryModel):
    """
    用户角色关联管理分页查询模型
    """

    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class SelectedRoleModel(RoleModel):
    """
    是否选择角色模型
    """

    flag: bool | None = Field(default=False, description='选择标识')


class UserRoleResponseModel(BaseModel):
    """
    用户角色关联管理列表返回模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    roles: list[SelectedRoleModel | None] = Field(default=[], description='角色信息')
    user: UserInfoModel = Field(description='用户信息')


class CrudUserRoleModel(BaseModel):
    """
    新增、删除用户关联角色及角色关联用户模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    user_id: int | None = Field(default=None, description='用户ID')
    user_ids: str | None = Field(default=None, description='用户ID信息')
    role_id: int | None = Field(default=None, description='角色ID')
    role_ids: str | None = Field(default=None, description='角色ID信息')
