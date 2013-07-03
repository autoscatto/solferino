solferino
=========

Python irc/retroshare bridge.

            attention this spaghetti code is especially disgusting, do not read if you're easily scared           

This blob is a bridge between retroshare lobbies and a irc chan.
Acts as a relay in both directions.

---

There are two concurrent threads (alert: with active waiting!!1ONE!)
each which handles messages in chan by his side, using two Queue (one for direction) in order to exchange them.



**TODO:**
  - implement in a smart way "event driven pyrs" which allows to throw all the unnecessary waiting in the toilet.
  - enter the logging and strengthen generating errors
  - turn it into a demon with all the necessary arrangements
  - manage connections / reconnections / reload
  - insert commands via chan from both sides
  - insert serious parsing of messages (oembed, other)
  - find someone who knows how to write code

Prepare
-------- 

```sh

git clone https://github.com/autoscatto/solferino.git
cd solferino
pip install irc
pip install html2text
python -O solferino.py "ircserver" "#ircchan"

```

Config
-----
create auth.txt with retroshare-nogui credential es:

    pwd yourpass
    port 7022
    user youruser
    host yourip

edit conf on top of solferino.py (only if you want to change nicknames, lobby name or timeouts)

Start
-----
```sh

python -O solferino.py "ircserver" "#ircchan"
profit

```


License
=========

```
            DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE
                    Version 2, December 2004

 Copyright (C) 2013 Romain Lespinasse <romain.lespinasse@gmail.com>

 Everyone is permitted to copy and distribute verbatim or modified
 copies of this license document, and changing it is allowed as long
 as the name is changed.

            DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE
   TERMS AND CONDITIONS FOR COPYING, DISTRIBUTION AND MODIFICATION

  0. You just DO WHAT THE FUCK YOU WANT TO.
```
