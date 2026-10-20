import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src import pipeline


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'incoming').mkdir()
        self.config = json.loads(Path('config/pipeline.json').read_text())
        self.config.update(required_columns=['municipio', 'porcentaje'], not_null_columns=['municipio'], numeric_ranges={'porcentaje': [0, 100]}, primary_key=['municipio'])
        self.path = self.root / 'config.json'
        self.path.write_text(json.dumps(self.config))
        env = patch.dict(os.environ, ETL_DATA_DIR=str(self.root), ETL_CONFIG_PATH=str(self.path))
        env.start()
        self.addCleanup(env.stop)

    def source(self, content):
        (self.root / 'incoming' / 'test.csv').write_text(content, encoding='utf-8')

    def test_pipeline_snapshot_and_deduplication(self):
        self.source('Municipio,Porcentaje\n Cali ,28.5\n Cali ,28.5\n')
        batch = pipeline.extract('test')
        self.source('cambiado\nvalor\n')
        self.assertEqual(batch, pipeline.extract('test'))
        pipeline.post_validate(pipeline.transform(pipeline.validate(batch)))
        report = json.loads((Path(batch) / 'post_validation.json').read_text())
        self.assertEqual(report['output_rows'], 1)
        self.assertEqual(report['duplicates_removed'], 1)

    def test_missing_sources(self):
        with self.assertRaises(ValueError):
            pipeline.extract('empty')

    def test_invalid_range_blocks_load(self):
        self.source('Municipio,Porcentaje\nCali,101\n')
        batch = pipeline.transform(pipeline.validate(pipeline.extract('range')))
        with self.assertRaises(ValueError):
            pipeline.post_validate(batch)
        self.assertFalse((Path(batch) / 'post_validation.json').exists())

    def test_duplicate_business_key(self):
        self.source('Municipio,Porcentaje\nCali,20\nCali,30\n')
        batch = pipeline.transform(pipeline.validate(pipeline.extract('keys')))
        with self.assertRaises(ValueError):
            pipeline.post_validate(batch)

    def test_bad_csv(self):
        self.source('Municipio,Porcentaje\nCali,20,extra\n')
        with self.assertRaises(ValueError):
            pipeline.validate(pipeline.extract('bad'))

    def test_tampered_snapshot(self):
        self.source('Municipio,Porcentaje\nCali,20\n')
        batch = pipeline.extract('tampered')
        next((Path(batch) / 'raw').glob('*.csv')).write_text('changed')
        with self.assertRaises(ValueError):
            pipeline.validate(batch)


if __name__ == '__main__':
    unittest.main()
