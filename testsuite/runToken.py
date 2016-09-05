#根据token码生成645协议帧，由于是该项目独有没有进行命令封装，以原始命令帧形式执行
tk = "0000 0000 0001 5099 7584"
token = "".join(tk.split())
token = dl645.splitByLen(token, [2] * 10)[::-1]
code = ['0C', '2C', 'CC', '04', '04', '00', '00', '00', '01', '00', '00', '00']
fm = "68 11 11 11 11 11 11 68 14 16".split() + dl645.add33H(code + token)
cs = dl645.getCheckSum(fm)
fm = fm + [cs] + ['16']
#print(fm)
cmd = ":raw " + " ".join(fm)
#print(cmd)

import time
for i in range(6):
  psend(cmd)
  time.sleep(20)

