from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text

from config.database import Base


class AiReqMessage(Base):
    """需求沟通群聊消息。"""

    __tablename__ = 'ai_req_message'
    __table_args__ = {'comment': 'AI需求沟通群聊消息'}

    msg_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='消息ID')
    room_id = Column(Integer, nullable=False, server_default='1', index=True, comment='房间ID')
    user_id = Column(BigInteger, nullable=False, index=True, comment='发送人，0 为 Grok')
    user_name = Column(String(64), nullable=False, comment='账号')
    nick_name = Column(String(64), nullable=True, comment='昵称')
    role = Column(String(16), nullable=False, server_default="'user'", comment='user/ai/system')
    content = Column(Text, nullable=False, comment='正文')
    create_time = Column(DateTime, nullable=True, default=datetime.now, index=True, comment='发送时间')


class AiReqItem(Base):
    """AI 需求清单条目。"""

    __tablename__ = 'ai_req_item'
    __table_args__ = {'comment': 'AI需求清单'}

    item_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='需求ID')
    title = Column(String(200), nullable=False, comment='标题')
    detail = Column(Text, nullable=True, comment='说明')
    priority = Column(String(8), nullable=True, server_default="'P2'", comment='P1/P2/P3')
    status = Column(
        String(16),
        nullable=False,
        server_default="'pending'",
        index=True,
        comment='pending/developing/testing/done/cancelled',
    )
    source_msg_id = Column(BigInteger, nullable=True, comment='来源消息')
    created_by = Column(BigInteger, nullable=True, comment='创建人')
    created_by_name = Column(String(64), nullable=True, comment='创建人名称')
    remark = Column(String(500), nullable=True, comment='备注')
    create_time = Column(DateTime, nullable=True, default=datetime.now, index=True, comment='创建时间')
    update_time = Column(DateTime, nullable=True, default=datetime.now, comment='更新时间')
