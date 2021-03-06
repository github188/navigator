﻿# !/usr/bin/python3.4

import re
import math
import time

# 本地模块
import rs485
import lib645

# helper function
def splitByLen(string, len_list):
    """根据长度列表分割字符串

    string: 要分割的字符串
    len_list:字符串长度列表
    如string="1234567890",len_list=[2,4,3,1]
    则函数返回['12', '3456', '789', '0']
    """
    current_index = 0
    new_list = []
    for i in len_list:
        if (current_index < len(string)):
            new_list.append(string[current_index:(current_index + i)])
            current_index += i
    return new_list

def minus33H(data_list):
    """数据域作减33h处理，接收数据使用

    data_list:[xx,xx,xx,...]
    """
    fm = data_list

    # 减33h等于加上33h的补码cdh，补码为反码加1
    tem = [math.fmod( ( int(i, 16) + int('cd', 16) ), 256) for i in fm]
    for i in range(len(tem)):
        #十进制格式化为十六进制显示,format参数不能为float类型
        tem[i] = "{0:02X}".format( int( tem[i] ) )
    return tem

def add33H(data_list):
    """数据域作加33h处理，发送数据使用

    参数列表:
    data_list:[xx,xx,xx,...]
    """
    data_area = [math.fmod((int(i, 16) + int('33', 16)), 256) for i in data_list]
    for i in range(len(data_area)):
    #十进制格式化为十六进制显示,format参数不能为float类型
        data_area[i] = "{0:02X}".format( int( data_area[i] ) )
    return data_area

def getCheckSum(frame_list):
    """根据用户输入的帧信息计算出校验和，并返回计算的校验和的值，以16进制字符串形式返回

    参数列表：
    frame_list: 存放需要参与校验和计算的帧信息列表
    如['68', '11', '11', '11', '11', '11', '11', '68',
		    '11', '04', '35', '34', '33', '37']
    校验和计算方法：等于除结束符、校验码以外的所有字节的十进制数之和与256的模,以十六进制形式体现在报文中
    """
    #建立frame_list的副本，防止修改帧的内容
    copy = list(frame_list)
    # 将copy后的list值转换为10进制
    copy = [int(i, 16) for i in copy]
    #计算的校验和并格式化为16进制字符串数组返回
    return ["{0:02X}".format(int(math.fmod(sum(copy[:]), 256)))]

def isValid(frame):
    """检查帧起始符、结束符、校验和，判断是否是有效帧

    帧有效性检查项：
        检查帧起始符、结束符、校验码是否是正确的值，
    正确则报文有效，返回True，否则报文无效，返回False
    """
    #协议最短帧长为12字节，不足12字节直接返回None
    if len(frame) < 12:
        return False

    #起始符、结束符错误直接返回None
    if (frame[0] != '68') or (frame[7] != '68') or (frame[-1] != '16'):
        return False

    #数据域长度和实际数据域长度不符直接返回None
    if int(frame[9], 16) != len(frame[10:-2]):
        return False

    #校验码错误直接返回None
    if getCheckSum(frame[0:-2]) != [frame[-2]]:
        return False
    return True

class Meter():
    def __init__(self, matchCmd = {}, cmdin = ""):
        self.protocol = matchCmd
        # 密码 PA PA0 PA1 P2
        self.pwd = "04222222"
        # 操作者代码
        self.opcode = "01000000"
        # 后续帧的帧序号
        self.seq = 0
        # 通信地址 默认为['11','11','11','11','11','11']
        self.addr = ['11','11','11','11','11','11']
        # 返回数据 默认为[], 如包含后续数据的操作需返回所有的解析数据，而不仅是某一次的数据
        self.all_data = []
        """ 提取输入的命令信息：命令名称、参数、附加参数

        举例：
        command ":get-energy 00000000"
        返回值: [':get-energy', '00000000']

        命令的封装格式包含如下三种:
        :get-xxxx             //1.抄读命令，无参数
        :get-xxxx XXXXXXXX    //2.抄读命令、参数
        :get-xxxx XXXXXXXX add-XXXXX  //3.抄读命令、参数、附加参数
        :set-xxxx XXXXXXXX    //4.设置命令、参数
        """
        self.cmd = cmdin.split()

    def modifyCmd(self, matchCmd, cmdin):
        # self.protocol为匹配的协议封装模板
        self.protocol = matchCmd
        self.cmd = cmdin.split()

    def getPwd(self):
        return self.pwd

    def getOpcode(self):
        return self.opcode

    def getItemName(self):
        """解析输入命令的数据项名称并返回

        如:get-energy 00000000 表示抄读 (当前)组合有功总电能
        """
        # 0-读数据
        if self.protocol['type'] == 0:
            return eval(self.protocol['txInfo'])(self.cmd[1])
        if self.protocol['type'] == 2:
            return eval(self.protocol['txInfo'])(self.cmd[2], self.cmd[1])

    def buildFrame(self):
        """生成发送帧

        发送帧的生成思路为：
        :get-xxxx
          1.抄读命令，无参数：所需参数：表地址 + 数据标识
          2.数据标识：协议中已有 self.protocol['id']
        :get-xxxx XXXXXXXX
          1.抄读命令、参数：所需参数：表地址 + 数据标识
          2.数据标识：参数中提取 self.cmd[1]
          3.表地址: 调用函数获取 self.getAddr()
        :get-xxxx XXXXXXXX add-XXXXX
          1.抄读命令、参数、附加参数：所需参数：表地址 + 数据标识 + 附加参数
          2.数据标识：参数中提取 self.cmd[1]
          3.附加参数：从附加参数中提取 self.cmd[2]
          4.表地址: 调用函数获取 self.getAddr()
        :set-xxxx XXXXXXXX    //4.设置命令、参数
          TODO: 待完善
        """
        # 原始命令帧直接返回self.cmd即为发送帧
        if self.protocol['type'] == 20:  # 20-原始发送帧
            self.tx = self.cmd
            return self.tx
        else:
            #'68':起始符
            new_frame = ['68']
            # 通信地址：反序
            new_frame.extend(self.addr[::-1])
            #'68':起始符
            new_frame.extend(['68'])

            # 根据协议帧的如下类型进行分别处理
            #  0- 读数据
            #  1- 读后续数据
            #  2- 写数据
            #  3- 读通信地址
            #  4- 写通信地址
            #  5- 广播校时
            #  6- 冻结命令
            #  7- 更改通信速率
            #  8- 修改密码
            #  9- 最大需量清零
            #  10- 电表清零
            #  11- 事件清零
            #  20- 原始命令帧
            if self.protocol['type'] == 0:
                # 功能码: 11为抄读数据
                new_frame.extend(['11'])
                # 数据域长度
                if self.protocol.get("add"):
                    add_len = len(self.cmd[2][4:]) // 2
                    new_frame.extend(['{0:02X}'.format(4 + add_len)])
                else:
                    new_frame.extend(['04'])
                # 数据标识：数据标识从参数即self.cmd[1]中提取 加33H 反序
                new_frame.extend(add33H(splitByLen(self.cmd[1], [2] * 4)[::-1]))
                # 附件参数: 如果需要附加参数的话
                if self.protocol.get("add"):
                    new_frame.extend(add33H(splitByLen(self.cmd[2][4:],
                                                        [2] * add_len)[::-1]))
            elif self.protocol['type'] == 1:
                # 功能码: 12为抄读后续数据
                new_frame.extend(['12'])
                # 数据域长度
                new_frame.extend(['05'])
                # 数据标识：数据标识从参数即self.cmd[1]中提取 加33H 反序
                new_frame.extend(add33H(splitByLen(self.cmd[1], [2] * 4)[::-1]))
                # 帧序号
                new_frame.extend(add33H(["{0:02X}".format(self.seq)]))
            elif self.protocol['type'] == 2:
                # 功能码: 14为写数据
                new_frame.extend(['14'])
                # 数据域长度
                new_frame.extend(["{0:02X}".format(12 + len(self.cmd[2]) // 2)])
                # 数据标识：加33H 反序
                new_frame.extend(add33H(splitByLen(self.cmd[1], [2] * 4)[::-1]))
                # 密码：加33H 正序
                new_frame.extend(add33H(splitByLen(self.getPwd(), [2] * 4)))
                # 操作者代码：加33H 正序
                new_frame.extend(add33H(splitByLen(self.getOpcode(), [2] * 4)))
                # 设定值
                # 有些协议命令的设置参数反序比较特殊，在协议模板中增加
                # reverse_setting_data进行单独处理
                if self.protocol.get("reverse_setting_data"):
                    setting_list = eval(self.protocol['reverse_setting_data'])(self.cmd[2])
                else:
                    setting_list = splitByLen(self.cmd[2],
                                    [2] * (len(self.cmd[2]) // 2))[::-1]
                new_frame.extend(add33H(setting_list))
            elif self.protocol['type'] == 3:
                new_frame = ['68', 'AA', 'AA', 'AA', 'AA', 'AA', 'AA', '68',
                             '13', '00']

            # 校验和
            new_frame.extend(getCheckSum(new_frame))
            #'16':结束符
            new_frame.extend(['16'])
            self.tx = new_frame
            return new_frame

    def send(self, rs485):
        result = rs485.sendToCOM(self.tx)
        self.rx = rs485.getFromCom()
        return result

    def response(self):
        return self.rx

    def responseInfo(self):
        """命令返回信息提取，正常应答、异常应答及相应的错误信息、无应答

        """
        if len(self.rx) == 0:
            return "无应答..."
        elif int(self.rx[8], 16) & 0xD0 == 0xD0:
            result = "异常应答帧"
            err = int(minus33H([self.rx[-3]])[0], 16)
            if err & 0x01:
                result += ">>其他错误"
            if err & 0x02:
                result += ">>无请求数据"
            if err & 0x04:
                result += ">>密码错/未授权"
            if err & 0x08:
                result += ">>通信速率不能更改"
            if err & 0x10:
                result += ">>年时区数超"
            if err & 0x20:
                result += ">>日时段数超"
            if err & 0x40:
                result += ">>费率数超"
            return result
        else:
            return "操作成功!"

    def responseData(self):
        """提取返回帧中的数据信息并返回

        返回值：以字符串数组形式返回
        TODO: zx 解决数据的正负号显示问题
        """
        data_area = minus33H(self.rx[10:-2])
        # 0-读数据  需要解析数据域
        if (self.protocol['type'] == 0 or
            self.protocol['type'] == 1 or
            self.protocol['type'] == 3):
            self.data_list = eval(self.protocol['rxInfo'])(data_area)
            if self.protocol['type'] == 3:
                self.addr = data_area[::-1]
        # 20-原始发送帧, 2-写数据  不需要解析数据域
        elif (self.protocol['type'] == 20 or
              self.protocol['type'] == 2):
            self.data_list = ''
        return self.data_list

    def toPrint(self):
        show = []
        if self.getItemName():
            show.append(self.getItemName())
        show.append("发:" + " ".join(self.tx))
        show.append("收:" + " ".join(self.rx))
        show.append(self.responseInfo())

        if isValid(self.rx):
            data_list = self.responseData()
            show.append("\n".join(data_list))
            # 将返回数据扩展到返回数据列表中
            self.all_data.extend(data_list)
        elif len(self.rx) > 0:
            show.append("接收帧格式非法!")
        return show

def stampTime():
    print("{:=^80}".format(time.strftime("[%Y-%m-%d %H:%M:%S]")))

def runCmd(command, followup = False):
    """ TODO: 详细梳理运行流程

    followup: 是否为后续帧标志
    """
    # 非后续帧才需要去匹配输入命令，否则不用匹配
    if not followup:
        # step 1: 从命令封装库中查找是否有有匹配的命令
        CMD.matchCmdModel = None
        for item in lib645.CMDS:
            if re.match(item['pattern'], command):
                CMD.matchCmdModel = item
                break
        # 匹配成功，将将匹配封装协议信息写入self.protocol
        # command分割后写入self.cmd
        if CMD.matchCmdModel:
            CMD.modifyCmd(CMD.matchCmdModel, command)
            # 此时相当于重新执行一个新的命令，需要清空返回数据
            CMD.all_data = []

    # step 2：匹配成功则执行命令
    if CMD.matchCmdModel:
        CMD.buildFrame()

        # step 3：数据准备就绪后向串口发送命令
        result = CMD.send(rs485.mRS)

        # step 4: 串口未返回error则继续执行
        if result != 'error':
            rx = CMD.response()
            show = CMD.toPrint()
            stampTime()
            for line in show:
                print(line)

            if "操作成功!" in CMD.responseInfo():
                # 有后续数据
                if (CMD.rx[8] == "B2" or
                    CMD.rx[8] == "B1"):
                    CMD.protocol['type'] = 1  # 修改操作类型为读后续数据
                    CMD.seq += 1
                    runCmd(command, followup = True)
                # 不再有无后续数据情况下需恢复参数
                elif CMD.rx[8] == "92":
                    # 恢复协议类型为0-读数据，充值seq=0
                    CMD.protocol['type'] = 0
                    CMD.seq = 0

                # 如果解析数据有值则返回
                return CMD.all_data

    # step 2: 匹配不成功输出错误提示
    else:
        stampTime()
        print("命令格式错误，请检查！！！")

# 创建类Meter的全局对象，程序运行中只创建一个实例
CMD = Meter()
# 创建模块lib645定义的类ID的实例
id = lib645.Id()

if __name__ == '__main__':

    ### test code ###
    #发：68 11 11 11 11 11 11 68 11 04 33 33 33 33 17 16
    #收：68 11 11 11 11 11 11 68 91 08 33 33 33 33 68 39 33 33 A2 16

    # for i in range(10):
    #     cmdin = ":get-energy 00010000"
    #     runCmd(cmdin)
    #     time.sleep(1)

    command = ":get-energy 000aFf0C"
    # step 1: 从命令封装库中查找是否有有匹配的命令
    matchCmdModel = None
    for item in lib645.CMDS:
        if re.match(item['pattern'], command):
            matchCmdModel = item
            break

    # step 2：匹配成功则执行命令
    if matchCmdModel:
        CMD.modifyCmd(matchCmdModel, command)
        print(CMD.getItemName())
