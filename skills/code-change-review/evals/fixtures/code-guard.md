# Offline PR artifacts

用户请求：复核这条并发覆盖意见，结合当前完整变更判断是否有问题。只读，不执行代码、访问外部服务或修改文件。example/accounts，base=b2，head=h2；下列为完整相关实现。数据库事务和锁语义已核实，不存在未提供的旁路写入口。

原评论称：X/Reddit 没有外层去重锁，两个首次添加请求会覆盖创建人，应在外层再加锁。

server/accounts/repository.py（候选文件行号）：
1 def add(conn, platform, key, actor):
2     if platform in {"x", "reddit"}:
3         return upsert_social(conn, platform, key, actor)
4     with lock_for(conn, platform, key):
5         return insert_or_update(conn, platform, key, actor)

server/accounts/social.py（候选文件行号）：
1 def upsert_social(conn, platform, key, actor):
2     with lock_for(conn, platform, key):
3         return insert_or_update(conn, platform, key, actor)

lock_for 是本事务范围的数据库排他锁，键为 platform/key。insert_or_update 在同一连接和事务内读取：不存在则 INSERT creator=actor；已存在仅更新其他允许字段，不修改 creator。基线也采用这套内部锁，本 PR 只增加普通平台外层锁。

作者报告双连接同键测试：创建人保持首次写入者；本轮尚未执行该测试。没有其他未解决意见或合并必需的验证缺口。
