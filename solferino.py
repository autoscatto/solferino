#!/usr/bin/python

import sys
import argparse
import itertools
import irc.client
import Queue
import threading
import pyrs.comms
import pyrs.rpc
import pyrs.msgs
import time
from pyrs.proto import core_pb2
from pyrs.proto import peers_pb2
from pyrs.proto import system_pb2
from pyrs.proto import chat_pb2
import pyrs.test.auth
import html2text

# This will load auth parameters from file 'auth.txt'
# ONLY use for tests - make the user login properly.
auth = pyrs.test.auth.Auth()

#----------------------------------------------------------------------------
#### bot nickname retroshare side
NICK_R="buzzisha"

#### bot nickname irc side
NICK_I="buzzirco"

TIMEOUT=2

#### retroshare bridged lobbies (exact name)
BRIDGECHAN="btest"

#### number of retry for join to retroshare lobbie

RETRYN=10

#----------------------------------------------------------------------------

LOBBIES={}


timeout = 0.5

q_i2r = Queue.Queue(maxsize=0)
q_r2i = Queue.Queue(maxsize=0)
target = None






def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('server')
    parser.add_argument('target', help="a nickname or channel")
    parser.add_argument('-p', '--port', default=6667, type=int)
    return parser.parse_args()

def printazza(connection):
            while not q_r2i.empty():
                nick,nmsg= q_r2i.get()
                chanmsg="<%s>: %s" %(nick,nmsg)
                q_r2i.task_done()
                connection.privmsg(target,' '.join(chanmsg.split('\n')))
                time.sleep(timeout)


# IRC part
class IRCBotto(threading.Thread):

    def on_connect(self,connection, event):
        if irc.client.is_channel(target):
            connection.join(target)
            return

    def on_join(self,connection, event):
        connection.privmsg(target, "START")

    def on_disconnect(self,connection, event):
        raise SystemExit()

    def on_msg(self,connection, e):
            nick,nmsg=e.source.nick,e.arguments[0]
            q_i2r.put((nick,nmsg))

    def __init__(self,re):
        threading.Thread.__init__(self)
        global target
        args = get_args()
        target = args.target
        self.runevent=re
        self.client = irc.client.IRC()
        try:
            c = self.client.server().connect(args.server, args.port, NICK_R)
        except irc.client.ServerConnectionError:
            print(sys.exc_info()[1])
            raise SystemExit(1)

        c.add_global_handler("welcome", self.on_connect)
        c.add_global_handler("join", self.on_join)
        c.add_global_handler("disconnect", self.on_disconnect)
        c.add_global_handler("pubmsg", self.on_msg)

    def run(self):
        while self.runevent.is_set():
            printazza(self.client.connections[0]) #XXX: painful hack
            self.client.process_once(0.2) #TODO: here too busy waiting, is necessary to find a sensible way to make a event driven architecture
        print "bona bimbi [%s]" % self.__class__.__name__

    def stop(self):
        self.join()


# Retroshare part
class RetrhoshareBot(threading.Thread):

    def send_on_lobby(self,cmsg):
        rp = chat_pb2.RequestSendMessage()
        rp.msg.id.chat_type = self.chat_type
        rp.msg.id.chat_id = self.lobby_id
        rp.msg.msg = cmsg
        msg_id = pyrs.msgs.constructMsgId(core_pb2.CORE, core_pb2.CHAT, chat_pb2.MsgId_RequestSendMessage, False)
        req_id = self.rs.request(msg_id, rp)
        self.requests.append(req_id)

    def __init__(self,re):
        threading.Thread.__init__(self)
        self.parser = pyrs.msgs.RpcMsgs()
        self.comms = pyrs.comms.SSHcomms(auth.user, auth.pwd, auth.host, auth.port)
        self.comms.connect()
        self.rs = pyrs.rpc.RsRpc(self.comms) 
        self.lobby_id=""
        self.chat_type=chat_pb2.TYPE_LOBBY
        self.requests = []
        self.runevent=re
        self.next_req_cycle = []
        rp = chat_pb2.RequestChatLobbies()
        rp.lobby_set = chat_pb2.RequestChatLobbies.LOBBYSET_ALL
        msg_id = pyrs.msgs.constructMsgId(core_pb2.CORE, core_pb2.CHAT, chat_pb2.MsgId_RequestRegisterEvents, False)
        self.chat_register_id = self.rs.request(msg_id, rp)
        self.requests.append(self.chat_register_id)
        rp = chat_pb2.RequestSetLobbyNickname()
        rp.nickname = NICK_R
        msg_id = pyrs.msgs.constructMsgId(core_pb2.CORE, core_pb2.CHAT, chat_pb2.MsgId_RequestSetLobbyNickname, False)
        req_id = self.rs.request(msg_id, rp)
        self.requests.append(req_id)

        for peer_req_id in self.requests:
          ans = self.rs.response(peer_req_id, timeout)
          if ans:
              (msg_id, msg_body) = ans
              resp = self.parser.construct(msg_id, msg_body)
              if not resp:
                print "Unable to Parse Response"
          else:
              print "No Response!"
          
        self.requests = []
        self.chatevent_msg_id = pyrs.msgs.constructMsgId(core_pb2.CORE, core_pb2.CHAT, chat_pb2.MsgId_EventChatMessage, True)
        #TODO: to be reviewed completely, if no-gui is already connected, he tries RETRYN times unnecessarily and does not update the lobby_id required for proper operation!!!
        r=0
        while True:
                  print "Starting new fetch cycle"
                  if r> RETRYN:
                     return
                  rp = chat_pb2.RequestChatLobbies()
                  rp.lobby_set = chat_pb2.RequestChatLobbies.LOBBYSET_ALL
                  msg_id = pyrs.msgs.constructMsgId(core_pb2.CORE, core_pb2.CHAT, chat_pb2.MsgId_RequestChatLobbies, False)
                  print "Sending Request for ChatLobbies"
                  chat_listing_id = self.rs.request(msg_id, rp)
                  self.requests.append(chat_listing_id)
                  self.next_req_cycle = []
                  for peer_req_id in self.requests:
                    ans = self.rs.response(peer_req_id, timeout)
                    if ans:
                      (msg_id, msg_body) = ans
                      resp = self.parser.construct(msg_id, msg_body)
                      if resp:
                        if (peer_req_id == chat_listing_id):
                          for lobby in resp.lobbies:
                            if lobby.lobby_state == chat_pb2.ChatLobbyInfo.LOBBYSTATE_PUBLIC:
                              LOBBIES[lobby.lobby_name]=lobby.lobby_id
                              if lobby.lobby_name == BRIDGECHAN:  #when I arrived here, I found the chat lobby was looking for, is now to take the id
                                  print ""
                                  print "-"*20
                                  print "Sending Request to Join Public ChatLobby %s" % (lobby.lobby_name)
                                  self.lobby_id=lobby.lobby_id
                                  print "-"*20
                                  req_id = self.join_leave(lobby.lobby_id,True)
                                  self.next_req_cycle.append(req_id)
                                  return
                            else:
                              sys.stdout.write("[.]")
                      else:
                        sys.stdout.write("[Unable to Parse Response]")
                  
                    else:
                      sys.stdout.write("No Response!")
                      continue
                  self.requests = self.next_req_cycle
                  r=r+1



    def join_leave(self,lid,join):
         rp = chat_pb2.RequestJoinOrLeaveLobby()
         rp.lobby_id = lid
         if join:
            rp.action = chat_pb2.RequestJoinOrLeaveLobby.JOIN_OR_ACCEPT
         else:
            rp.action = chat_pb2.RequestJoinOrLeaveLobby.LEAVE_OR_DENY 
         msg_id = pyrs.msgs.constructMsgId(core_pb2.CORE, core_pb2.CHAT, chat_pb2.MsgId_RequestJoinOrLeaveLobby, False)
         req_id = self.rs.request(msg_id, rp)
         return req_id



    def run(self):
            while self.runevent.is_set():
                  while not q_i2r.empty(): #if have stuff in the queue send it!
                        nick,nmsg=q_i2r.get()
                        cmsg= "<%s>: %s"%(nick,nmsg)
                        self.send_on_lobby(cmsg)
                        q_i2r.task_done()
                  try:
                    time.sleep(timeout)    ## TODO: this is the most controversial. In fact makes active waiting with timeout range
                  except KeyboardInterrupt: ## TODO manage somehow termination
                    inp = raw_input( 'prompt$ ' )
                    if(inp in ["Exit","exit","Quit","quit"] ):
                        break
                    if(inp in ["listlobbies"]):
                        print LOBBIES.keys()

                  ans = self.rs.response(self.chat_register_id, timeout)
                  if ans:
                    try:
                        (msg_id, msg_body) = ans
                        resp = self.parser.construct(msg_id, msg_body)

                        msgbody=html2text.html2text(resp.msg.msg)
                        q_r2i.put( (resp.msg.peer_nickname,msgbody))
                    except:
                        pass
            print "bona bimbi [%s]" % self.__class__.__name__

    def stop(self):
        self.comms.close()
        self.join()



if __name__ == '__main__':
    run_event = threading.Event()
    run_event.set()
    t1 = RetrhoshareBot(run_event)
    t2 = IRCBotto(run_event)
    t1.start()
    t2.start()

    try:
        while 1:
            time.sleep(.1)
    except KeyboardInterrupt:
        print "attempting to close threads. "
        run_event.clear()
        t1.join()
        t2.join()
        print "threads successfully closed"


