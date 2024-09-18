# ==================================================================================
#  Copyright (c) 2020 HCL Technologies Limited.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# ==================================================================================

"""
This Module is temporary for pushing data into influxdb before dpeloyment of QP xApp. It will depreciated in future, when data will be coming through KPIMON
"""

import datetime
import time
import pandas as pd
from influxdb_client import InfluxDBClient, WriteApi, WriteOptions
from configparser import ConfigParser
from mdclogpy import Logger

logger = Logger(name=__name__)

class DATABASE(object):

    def __init__(self, dbname='Timeseries', host="10.109.234.168", port='80', token='qhIq6TFXk0ndJrHQAlzrjvWXq9laFBGu', org='influxdata'):
        self.host = host
        self.port = port
        self.token = token
        self.org = org
        self.dbname = dbname
        self.client = None
        self.config()

    def connect(self):
        if self.client is not None:
            self.client.close()

        try:
            self.client = InfluxDBClient(
                url=f"http://{self.host}:{self.port}",
                token=self.token,
                org=self.org
            )
            version = self.client.version()
            logger.info("Connected to Influx Database, InfluxDB version: {}".format(version))
            return True

        except Exception as e:
            logger.error("Failed to establish a new connection with InfluxDB. Error: {}".format(e))
            time.sleep(120)

    def config(self):
        cfg = ConfigParser()
        cfg.read('src/qp_config.ini')
        for section in cfg.sections():
            if section == 'influxdb':
                self.host = cfg.get(section, "host")
                self.port = cfg.get(section, "port")
                self.token = cfg.get(section, "token")
                self.org = cfg.get(section, "org")
                self.dbname = cfg.get(section, "database")
                self.cellmeas = cfg.get(section, "cellmeas")

class INSERTDATA(DATABASE):

    def __init__(self):
        super().__init__()
        self.connect()

    def createdb(self, dbname):
        print("Create database: " + dbname)
        self.client.create_database(dbname)

    def dropdb(self, dbname):
        print("DROP database: " + dbname)
        self.client.drop_database(dbname)

    def dropmeas(self, measname):
        print("DROP MEASUREMENT: " + measname)
        self.client.query(f'DROP MEASUREMENT {measname}')

    def assign_timestamp(self, df):
        steps = df['measTimeStampRf'].unique()
        write_api = self.client.write_api(write_options=WriteOptions(batch_size=1))
        for timestamp in steps:
            d = df[df['measTimeStampRf'] == timestamp]
            d.index = pd.date_range(start=datetime.datetime.now(), freq='1ms', periods=len(d))
            write_api.write(bucket=self.dbname, record=d, data_frame_measurement_name=self.cellmeas)
            time.sleep(0.4)


def populatedb():
    # initiate connection and create database UEDATA
    db = INSERTDATA()
    df = pd.read_csv('src/cells.csv')
    print("Writing data into InfluxDB")
    while True:
        db.assign_timestamp(df)


if __name__ == "__main__":
    populatedb()


# import datetime
# import time
# import pandas as pd
# from src.database import DATABASE
# from configparser import ConfigParser


# class INSERTDATA(DATABASE):

#     def __init__(self):
#         super().__init__()
#         self.connect()

#     def createdb(self, dbname):
#         print("Create database: " + dbname)
#         self.client.create_database(dbname)
#         self.client.switch_database(dbname)

#     def dropdb(self, dbname):
#         print("DROP database: " + dbname)
#         self.client.drop_database(dbname)

#     def dropmeas(self, measname):
#         print("DROP MEASUREMENT: " + measname)
#         self.client.query('DROP MEASUREMENT '+measname)

#     def assign_timestamp(self, df):
#         steps = df['measTimeStampRf'].unique()
#         for timestamp in steps:
#             d = df[df['measTimeStampRf'] == timestamp]
#             d.index = pd.date_range(start=datetime.datetime.now(), freq='1ms', periods=len(d))
#             self.client.write_points(d, self.cellmeas)
#             time.sleep(0.4)


# def populatedb():
#     # inintiate connection and create database UEDATA
#     db = INSERTDATA()
#     df = pd.read_csv('src/cells.csv')
#     print("Writinig data into influxDB")
#     while True:
#         db.assign_timestamp(df)


# if __name__ == "__main__":
#     populatedb()
