# ==================================================================================
#       Copyright (c) 2020 AT&T Intellectual Property.
#       Copyright (c) 2020 HCL Technologies Limited.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#          http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
# ==================================================================================
"""
qp module main -- using Time series ML predictor

RMR Messages:
 #define TS_UE_LIST 30000
 #define TS_QOE_PREDICTION 30002
30000 is the message type QP receives from the TS;
sends out type 30002 which should be routed to TS.

"""
import os
import json
import logging
from mdclogpy import Logger
from ricxappframe.xapp_frame import RMRXapp, rmr
from prediction import forecast
from qptrain import train
from database import DATABASE, DUMMY
from exceptions import DataNotMatchError
import warnings
# import schedule
warnings.filterwarnings("ignore")

# pylint: disable=invalid-name
qp_xapp = None
db = None
logger = Logger(name=__name__)


def post_init(self):
    """
    Function that runs when xapp initialization is complete
    """
    self.predict_requests = 0
    logger.debug("QP xApp started")


def qp_default_handler(self, summary, sbuf):
    """
    Function that processes messages for which no handler is defined
    """
    logger.debug("default handler received message type {}".format(summary[rmr.RMR_MS_MSG_TYPE]))
    # we don't use rts here; free this
    self.rmr_free(sbuf)


def qp_predict_handler(self, summary, sbuf):
    """
    Function that processes messages for type 30000
    """
    logger.debug("predict handler received payload {}".format(summary[rmr.RMR_MS_PAYLOAD]))
    print("step 0")
    pred_msg = predict(summary[rmr.RMR_MS_PAYLOAD])
    print("step 1")
    self.predict_requests += 1
    print("step 2")
    # we don't use rts here; free this
    self.rmr_free(sbuf)
    print("step 3")
    success = self.rmr_send(pred_msg.encode(), 30002)
    print("step 4")
    logger.debug("Sending message to ts : {}".format(pred_msg))  # For debug purpose
    if success:
        logger.debug("predict handler: sent message successfully")
    else:
        logger.warning("predict handler: failed to send message")


def cells(ue):
    """
        Extract neighbor cell id for a given UE
    """
    db.read_data(ueid=ue)
    df = db.data
    cells = []
    if df is not None:
        nbc = df.filter(regex=db.nbcells).values[0].tolist()
        srvc = df.filter(regex=db.servcell).values[0].tolist()
        cells = srvc+nbc
    return cells

def sanitize_payload(payload):
    """
    Sanitize and correct common formatting issues in the payload.
    """
    try:
        # Remove leading and trailing whitespace
        payload = payload.strip()

        if payload.startswith('['):
            if not payload.endswith(']'):
                payload = payload.rstrip(',') + ']'
        
        # Handle case where payload might end with incomplete JSON structures
        if payload.endswith(','):
            payload = payload.rstrip(',')
        
        # Balance the brackets
        open_braces = payload.count('{')
        close_braces = payload.count('}')

        payload += ']'  # Add a closing bracket to ensure valid JSON

        if open_braces > close_braces:
            payload += '}' * (open_braces - close_braces)
        
        open_brackets = payload.count('[')
        close_brackets = payload.count(']')
        if open_brackets > close_brackets:
            payload += ']' * (open_brackets - close_brackets)
        
        # Ensure the payload ends with the correct character if it's an array
        if payload.startswith('[') and not payload.endswith(']'):
            payload += ']'
        
        # Ensure the payload ends with the correct character if it's an object
        if payload.startswith('{') and not payload.endswith('}'):
            payload += '}'
        
        # Validate JSON structure  
        try:
            json.loads(payload)  # Attempt to parse JSON to validate
        except json.JSONDecodeError:
            logging.error("Sanitized payload is still invalid JSON")
            return payload
        
        return payload
    
    except Exception as e:
        logging.error(f"Error sanitizing payload: {e}")
        return payload

def process_chunk(chunk):
    """
    Process a chunk of the payload and return predictions.
    """
    output = {}
    print("chunk: ", chunk)
    for ueid in chunk:
        tp = {}
        cell_list = cells(ueid)
        for cid in cell_list:
            train_model(cid)
            mcid = cid.replace('/', '')
            db.read_data(cellid=cid, limit=101)
            if db.data is not None and len(db.data) != 0:
                try:
                    inp = db.data[db.thptparam]
                except DataNotMatchError:
                    logger.debug("UL/DL parameters do not exist in provided data")
                df_f = forecast(inp, mcid, 1)
                if df_f is not None:
                    tp[cid] = df_f.values.tolist()[0]
                    df_f[db.cid] = cid
                    db.write_prediction(df_f)
                else:
                    tp[cid] = [None, None]
        output[ueid] = tp
    return output

def predict(payload, chunk_size=10000):
    """
    Function that forecasts the time series.
    Handles large payloads by processing in chunks.
    """
    output = {}

    try:
        # Decode bytes if necessary
        if isinstance(payload, bytes):
            payload = payload.decode('utf-8')
        
        print("step 5")
        payload = payload.strip()  # Strip any leading or trailing whitespace

        print("step 6")
        # Sanitize payload
        # wait until the sanitize_payload function is implemented

        payload = sanitize_payload(payload)
        
        print("step 7")
          
        # Validate payload structure
        # if not payload.startswith('{') or not payload.endswith('}'):
        #     logging.error(f"Invalid JSON payload structure: {payload[:2048]}")
        #     return json.dumps({"error": "Invalid JSON payload"})

        # Parse JSON payload
        payload = json.loads(payload)
        
    except json.JSONDecodeError as e:
        logging.error(f"JSONDecodeError: {e} with payload snippet: {payload[:2048]}")
        return json.dumps({"error": "Invalid JSON payload"})
    except Exception as e:
        logging.error(f"Error decoding payload: {e}")
        return json.dumps({"error": "Error processing payload"})
    
    ue_list = payload.get('UEPredictionSet', [])
    print("ue_list: ", ue_list)
     
    for ueid in ue_list:
        tp = {}
        cell_list = cells(ueid)
        for cid in cell_list:
            train_model(cid)
            mcid = cid.replace('/', '')
            db.read_data(cellid=cid, limit=101)
            if db.data is not None and len(db.data) != 0:
                try:
                    inp = db.data[db.thptparam]
                except DataNotMatchError:
                    logger.debug("UL/DL parameters do not exist in provided data")
                df_f = forecast(inp, mcid, 1)
                if df_f is not None:
                    tp[cid] = df_f.values.tolist()[0]
                    df_f[db.cid] = cid
                    db.write_prediction(df_f)
                else:
                    tp[cid] = [None, None]
        output[ueid] = tp
    return json.dumps(output)

# def predict(payload):
#     """
#     Function that forecast the time series
#     """
#     output = {}
#     try:
#         payload = json.loads(payload)
#     except json.JSONDecodeError as e:
#         logging.error(f"JSONDecodeError: {e}")
#         return json.dumps({"error": "Invalid JSON payload"})
    
#     ue_list = payload.get('UEPredictionSet', [])
#     for ueid in ue_list:
#         tp = {}
#         cell_list = cells(ueid)
#         for cid in cell_list:
#             train_model(cid)
#             mcid = cid.replace('/', '')
#             db.read_data(cellid=cid, limit=101)
#             if db.data is not None and len(db.data) != 0:
#                 try:
#                     inp = db.data[db.thptparam]
#                 except DataNotMatchError:
#                     logger.debug("UL/DL parameters do not exist in provided data")
#                 df_f = forecast(inp, mcid, 1)
#                 if df_f is not None:
#                     tp[cid] = df_f.values.tolist()[0]
#                     df_f[db.cid] = cid
#                     db.write_prediction(df_f)
#                 else:
#                     tp[cid] = [None, None]
#         output[ueid] = tp
#     return json.dumps(output)


def train_model(cid):
    if not os.path.isfile('src/'+cid):
        train(db, cid)


def start(thread=False):
    """
    This is a convenience function that allows this xapp to run in Docker
    for "real" (no thread, real SDL), but also easily modified for unit testing
    (e.g., use_fake_sdl). The defaults for this function are for the Dockerized xapp.
    """
    logger.debug("QP xApp starting")
    global qp_xapp
    connectdb(thread)
    fake_sdl = os.environ.get("USE_FAKE_SDL", None)
    qp_xapp = RMRXapp(qp_default_handler, rmr_port=4560, post_init=post_init, use_fake_sdl=bool(fake_sdl))
    qp_xapp.register_callback(qp_predict_handler, 30000)
    qp_xapp.run(thread)


def connectdb(thread=False):
    # Create a connection to InfluxDB if thread=True, otherwise it will create a dummy data instance
    global db
    if thread:
        db = DUMMY()
    else:
        db = DATABASE()
    success = False
    while not success and not thread:
        success = db.connect()


def stop():
    """
    can only be called if thread=True when started
    TODO: could we register a signal handler for Docker SIGTERM that calls this?
    """
    global qp_xapp
    qp_xapp.stop()


def get_stats():
    """
    hacky for now, will evolve
    """
    global qp_xapp
    return {"PredictRequests": qp_xapp.predict_requests}
