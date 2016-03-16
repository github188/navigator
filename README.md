# navigator
a simple automatic test GUI tool for electrical meter.
一款轻量级的电能表自动化测试工具
================================================================================

本次重构实现目标：
1.通过json格式实现表计命令的存储和读取
2.实现表计命令可扩展，增加表计命令无需修改代码，一条命令一个封装，虽然命令比较多，但是
可以做到没有耦合
3.实现模块化，每个模块实现一组特定的功能
4.针对每个模块编写测试代码

包含模块及功能描述：
1.GUI显示模块navigator.py: 实现表计测试工具GUI界面
2.表计协议处理模块meter.py: 实现表计通信帧的生成及显示等处理
3.表计封装命令文件处理模块cmd.py: 实现表计封装命令的添加、读取、存储，采用json格式
4.485通信处理模块rs485.py: 实现表计485通信
5.日志记录模块log.py: 实现日志文件的记录
6.测试脚本处理模块testcase.py: 实现测试用例的保存、另存、读取

================================开发思路日志=====================================
20160303：
1.rs485.py:不管命令如何封装，最终发往电能表的都一个原始帧，
从485接收到的也是原始帧，所以首先实现一个485通信模块,对外提供如下接口：
  a-接收原始帧并发送到485口
  b-返回从485口读取的原始帧
  c-设置485端口通信参数
  d-抄读485端口通信参数

2.meter.py: 实现两个功能：
  a-解析封装命令生成发送帧
  b-提取返回帧的有效数据用于显示或运算
该模块的实现需要依赖协议库的模板设计

3.dl645.py:设计一个645协议库，暂定json格式，做到可以灵活的添加协议
命令，这样就要做到每个命令的模板都要通用性又要兼顾各种各样的协议格式，
同时还要做到对重复的协议格式进行压缩，如310中抄读电量的协议命令多达上千条，
其实格式都是相同的，有很大的压缩空间。由于协议命令各种各样，一下子很难设计出通用的模板，
建议可以先动起来，尝试适配几个命令，慢慢的体会提炼出灵活通用的协议库模板。

命令格式定义：
    [:get-XXXX] [xxxxxxxx] [add-]   
      必须         可选      可选(附加数据)
    [:set-XXXX] [xxxxxxxx]
      必须      可选（有|无）
命令包含三个类型:
    1.抄读命令：以":get"进行识别
    2.校时命令: 特殊命令，仅此一个
    3.写命令：以":set"进行识别(冻结、清零等归到写命令一类)
    4.如果有附加数据，以add-进行识别
4.navigator.py: 程序的GUI界面，主要包含脚本&命令的输入区、脚本&命令的执行结果输出区域，
分别实现命令&脚本的执行和显示，附件功能：打开&保存&另存测试脚本文件、日志文件的自动保存、
通信参数设置等。meter模块和GUI界面的接口就是从GUI界面提取输入的命令或脚本，然后执行命令
或脚本，命令输出的信息打印至GUI的输出结果区域。其中输出可以通过修改标准的输出接口来实现。
因此meter模块只需要对外提供一个执行命令或脚本的接口，接收参数为GUI界面的输入命令和脚本。
