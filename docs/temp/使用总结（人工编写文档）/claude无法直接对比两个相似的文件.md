情况：我发现了问题wechat channel 的问题，复制了一个副本然后在副本中修改。修改完成之后我让claude来对比这两个文件：
```
当前lifeprism\llm\channel\wechat\channel.py 存在严重的问题：1.
  session_id使用错误，这里将微信官方api的id作为了lifeprism使用的session_id 2. 逻辑混乱，从from_to_user_id ->
  session_id -> 解析为to_user_id 这个过程太过复杂 3.
  当前接受处理消息之后没有发送给微信！我当前进行了初步的修改写在了lifeprism\llm\channel\wechat\channel
  copy.py，查看我修改的是否正确，是否有错误
```
claude的错误：
1. 模型opus 4.7 （但是这个可能是中转站注水）：居然无法正确判断那些是我新修改的内容，那些是之前代码的内容，尽管我已经在prompt中写明了'我当前进行了初步的修改写在了lifeprism\llm\channel\wechat\channel copy.py'
2. minimax 2.7 同样的错误

而我在trae中使用 minimax2.7 能够识别出来我具体犯了什么错误，能够争取对比

总结：不知道claude到底是什么问题，越来越难用