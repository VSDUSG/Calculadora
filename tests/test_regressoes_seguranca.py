import unittest
from unittest.mock import patch

from fastapi import HTTPException
from pydicom.dataset import Dataset

from daikon import dicom_server, web


def consulta_mwl(data):
    identifier = Dataset()
    sps = Dataset()
    if data is not None:
        sps.ScheduledProcedureStepStartDate = data
    identifier.ScheduledProcedureStepSequence = [sps]
    return identifier


class WorklistDateTests(unittest.TestCase):
    @patch("daikon.dicom_server.database.query", return_value=[])
    def test_intervalo_fechado_usa_limites_inclusivos(self, query):
        dicom_server._consultar_worklist(consulta_mwl("20260610-20260612"))
        sql, params = query.call_args.args
        self.assertIn("a.data >= ?", sql)
        self.assertIn("a.data <= ?", sql)
        self.assertEqual(params, ["2026-06-10", "2026-06-12"])

    @patch("daikon.dicom_server.database.query", return_value=[])
    def test_data_exata_restringe_inicio_e_fim(self, query):
        dicom_server._consultar_worklist(consulta_mwl("20260610"))
        _, params = query.call_args.args
        self.assertEqual(params, ["2026-06-10", "2026-06-10"])

    @patch("daikon.dicom_server.database.query", return_value=[])
    def test_intervalos_abertos(self, query):
        dicom_server._consultar_worklist(consulta_mwl("-20260610"))
        sql, params = query.call_args.args
        self.assertNotIn("a.data >= ?", sql)
        self.assertIn("a.data <= ?", sql)
        self.assertEqual(params, ["2026-06-10"])

    @patch("daikon.dicom_server.database.query")
    def test_data_invalida_nao_expoe_agenda_sem_filtro(self, query):
        resultado = dicom_server._consultar_worklist(consulta_mwl("20261340"))
        self.assertEqual(resultado, [])
        query.assert_not_called()


class ReportImageTests(unittest.TestCase):
    @patch("daikon.web.database.query", return_value=[{"id": 10}])
    def test_aceita_somente_imagens_do_estudo(self, query):
        self.assertEqual(web._imagens_do_estudo(7, [10, "10"]), [10])
        self.assertEqual(query.call_args.args[1], (7, 10))

    @patch("daikon.web.database.query", return_value=[{"id": 10}])
    def test_rejeita_imagem_de_outro_estudo(self, _query):
        with self.assertRaises(HTTPException) as contexto:
            web._imagens_do_estudo(7, [10, 99])
        self.assertEqual(contexto.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
