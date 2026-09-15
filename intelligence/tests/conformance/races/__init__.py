"""竞态目录（INV-R6，运行底座 P4 / 工单 #31）。

每条竞态两种合法历史、两个顺序各一夹具；表在 ``catalog.py``，夹具按表分文件。
驱动靠 ``ContinuousAgentEpisode.manual_drive()`` 的五个步点把取消 / steer / close /
restore 精确插进两个效果之间——不用线程、不用 sleep，两序都是确定性的。
"""
