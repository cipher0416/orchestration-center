# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json

from database.utils.db_connection import create_connection
from database.utils.query_execution import execute_query
from orchestrate.core.model.execution_record import ExecutionRecord


def db_save_execution_record(record: ExecutionRecord) -> str:
    save_sql = """
               INSERT INTO execution_records
                   (execution_id, psop_id, psop_name, started_at, completed_at, status, step_count, record_content)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               """
    conn = create_connection()
    execute_query(conn, save_sql, (
        record.execution_id,
        record.psop_id,
        record.psop_name,
        record.started_at,
        record.completed_at,
        record.status,
        len(record.execution_history),
        record.model_dump_json(),
    ))
    conn.close()
    return record.execution_id


def db_list_execution_records():
    query_sql = """
                SELECT execution_id, psop_id, psop_name, started_at, completed_at,
                       status, step_count, record_content
                FROM execution_records ORDER BY started_at DESC
                """
    conn = create_connection()
    rows, _ = execute_query(conn, query_sql)
    conn.close()
    result = []
    for row in rows:
        summary = {
            "execution_id": row[0],
            "psop_id": row[1],
            "psop_name": row[2],
            "started_at": row[3].isoformat() if hasattr(row[3], 'isoformat') else row[3],
            "completed_at": row[4].isoformat() if hasattr(row[4], 'isoformat') else row[4],
            "status": row[5],
            "step_count": row[6],
            "error": None,
        }
        try:
            content = json.loads(row[7]) if row[7] else {}
            summary["error"] = content.get("error")
        except Exception:
            pass
        result.append(summary)
    return result


def db_get_execution_record(execution_id: str):
    query_sql = "SELECT record_content FROM execution_records WHERE execution_id = %s"
    conn = create_connection()
    results, _ = execute_query(conn, query_sql, (execution_id,))
    conn.close()
    if results and len(results) > 0:
        return ExecutionRecord.model_validate(json.loads(results[0][0]))
    return None


def db_delete_execution_record(execution_id: str) -> bool:
    delete_sql = "DELETE FROM execution_records WHERE execution_id = %s"
    conn = create_connection()
    _, error = execute_query(conn, delete_sql, (execution_id,))
    conn.close()
    return error is None
