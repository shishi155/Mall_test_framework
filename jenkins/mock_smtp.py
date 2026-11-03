# -*- coding: utf-8 -*-
"""极简 SMTP 服务器，用于本地验证邮件通知（不真正发信）。

用法: python jenkins/mock_smtp.py [端口]
输出: build/mock-mail/*.eml（每封信一个文件）
"""
from __future__ import annotations

import socketserver
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "build" / "mock-mail"
OUT.mkdir(parents=True, exist_ok=True)


class SMTPHandler(socketserver.StreamRequestHandler):
    def reply(self, line: str):
        self.wfile.write((line + "\r\n").encode())

    def handle(self):
        self.reply("220 mock-smtp ready")
        mail_from, rcpt, data_mode = "", [], False
        buf = []

        while True:
            raw = self.rfile.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")

            if data_mode:
                if line == ".":
                    data_mode = False
                    subject = ""
                    for b in buf:
                        if b.lower().startswith("subject:"):
                            subject = b[8:].strip()
                            break
                    name = time.strftime("%Y%m%d_%H%M%S") + f"_{len(list(OUT.glob('*.eml')))}.eml"
                    (OUT / name).write_text("\n".join(buf), encoding="utf-8")
                    print(f"[mock-smtp] 收到邮件 -> {name} | from={mail_from} to={rcpt} | {subject}")
                    buf = []
                    mail_from, rcpt = "", []
                    self.reply("250 OK queued")
                else:
                    buf.append(line)
                continue

            low = line.lower()
            if low.startswith("ehlo") or low.startswith("helo"):
                self.wfile.write(b"250-mock-smtp\r\n250-AUTH LOGIN PLAIN\r\n250 OK\r\n")
            elif low.startswith("auth login"):
                self.reply("334 VXNlcm5hbWU6")          # Username:
                self.rfile.readline()
                self.reply("334 UGFzc3dvcmQ6")          # Password:
                self.rfile.readline()
                self.reply("235 Authentication successful")
            elif low.startswith("auth plain"):
                self.reply("235 Authentication successful")
            elif low.startswith("mail from"):
                mail_from = line
                self.reply("250 OK")
            elif low.startswith("rcpt to"):
                rcpt.append(line)
                self.reply("250 OK")
            elif low.startswith("data"):
                data_mode = True
                self.reply("354 End data with <CR><LF>.<CR><LF>")
            elif low.startswith("quit"):
                self.reply("221 Bye")
                break
            else:
                self.reply("250 OK")


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 2525
    print(f"[mock-smtp] listening on 0.0.0.0:{port}, 邮件保存到 {OUT}")
    with Server(("0.0.0.0", port), SMTPHandler) as srv:
        srv.serve_forever()


if __name__ == "__main__":
    main()
