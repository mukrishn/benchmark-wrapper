#!/usr/bin/env python
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import os
import re
import subprocess
from datetime import datetime
import logging
import asyncio
import os
import argparse
import yaml
import json

logger = logging.getLogger("snafu")


class Trigger_trex():
    def __init__(self, args):
        self.uuid = args.uuid
        self.user = args.user
        self.resourcetype = args.resourcetype
        self.cluster_name = args.cluster_name
        self.duration = args.duration
        self.testpmd_node = args.testpmd_node
        self.trex_node = args.trex_node

    async def _run_asyncio(self, *args):
        # Create subprocess and stdout must a pipe to be accessible as process.stdout
        process = await asyncio.create_subprocess_shell(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        # Wait for the subprocess to finish
        stdout, stderr = await process.communicate()
        return stdout.strip().decode("utf-8"), stderr.strip().decode("utf-8"), process.returncode

    def _json_payload(self, data):
        payload = json.loads(data)
        for item in payload:
            item.update({"workload": "testpmd",
                        "uuid": self.uuid,
                        "user": self.user,
                        "cluster_name": self.cluster_name,
                        "kind": self.resourcetype,
                        "testpmd_node": self.testpmd_node,
                        "trex_node": self.trex_node,
                        "timestamp": datetime.fromtimestamp(float(item["ts_epoch"]))
                        })
        return payload

    def _run_trex(self):

        loop = asyncio.get_event_loop()
        # TRex non interactive command 
        trex_cmd = "./_t-rex-64 -i --no-hw-flow-stat" 
        # command to run burst script with a 10 sec buffer to trex service
        burst_cmd = "sleep 10 && run_simple_burst"
        # set sleep duration with 15 sec buffer
        sleep_duration = int(self.duration) + 20 
        # kill TRex service after duration with buffer
        kill_cmd = "sleep " + str(sleep_duration) + " && pkill _t-rex-64"

        commands = asyncio.gather(self._run_asyncio(trex_cmd), self._run_asyncio(burst_cmd), self._run_asyncio(kill_cmd))
        trex, burst, kill = loop.run_until_complete(commands)
            
        loop.close()        

        # return only TRex process 
        return burst[0], burst[1], burst[2]

    def emit_actions(self):
        logger.info("Starting TRex Traffic Generator..")
        stdout, stderr, rc = self._run_trex()
        if rc == 0:
            documents = self._json_payload(stdout)            
            for document in documents:
                yield document, 'results'
                logger.info(document)
            logger.info("Finished Generating traffic..")
        else:
            raise Exception("TRex failed to execute, stopping...")
            logger.critical("TRex failed to execute, stopping...")
            logger.critical("stdout: %s" % stdout)
            logger.critical("stderr: %s" % stderr)            
            exit(1)
