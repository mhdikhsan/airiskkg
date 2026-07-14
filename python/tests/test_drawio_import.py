"""Tests for the draw.io / diagrams.net XML importer."""

import base64
import zlib
from urllib.parse import quote

import pytest

from airiskkg.drawio_import import DrawioImportError, drawio_to_ttl

PLAIN_XML = """<mxfile host="app.diagrams.net">
  <diagram id="d1" name="Page-1">
    <mxGraphModel>
      <root>
        <mxCell id="0" /><mxCell id="1" parent="0" />
        <mxCell id="q" value="User Query" style="ellipse" vertex="1" parent="1"/>
        <mxCell id="vdb" value="Vector DB" style="shape=cylinder3" vertex="1" parent="1"/>
        <mxCell id="ret" value="Retrieve Chunks" style="rounded=0" vertex="1" parent="1"/>
        <mxCell id="llm" value="LLM" style="shape=hexagon" vertex="1" parent="1"/>
        <mxCell id="gen" value="Generate Answer" vertex="1" parent="1"/>
        <mxCell id="ans" value="Answer" style="ellipse" vertex="1" parent="1"/>
        <mxCell id="e1" edge="1" source="q" target="ret" parent="1"/>
        <mxCell id="e2" edge="1" source="vdb" target="ret" parent="1"/>
        <mxCell id="e3" edge="1" source="ret" target="gen" parent="1"/>
        <mxCell id="e4" edge="1" source="llm" target="gen" parent="1"/>
        <mxCell id="e5" edge="1" source="gen" target="ans" parent="1"/>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>"""


def test_plain_mxfile_imports_to_beam_ttl() -> None:
    ttl, warnings = drawio_to_ttl(PLAIN_XML)
    assert "ex:RetrieveChunks a beam:Process" in ttl
    assert "ex:Llm a beam:StatisticalModel" in ttl
    assert "ex:UserQuery a beam:Data" in ttl
    assert "beam:use ex:UserQuery" in ttl or "ex:UserQuery,\n        ex:VectorDb" in ttl
    assert "beam:produce ex:Answer" in ttl
    assert "beam:inform ex:GenerateAnswer" in ttl
    assert warnings  # every guessed type is reported


def test_compressed_diagram_imports() -> None:
    inner = """<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>
    <mxCell id="a" value="Training Data" style="ellipse" vertex="1" parent="1"/>
    <mxCell id="t" value="Train Model" vertex="1" parent="1"/>
    <mxCell id="m" value="Model" style="shape=hexagon" vertex="1" parent="1"/>
    <mxCell id="e1" edge="1" source="a" target="t" parent="1"/>
    <mxCell id="e2" edge="1" source="t" target="m" parent="1"/>
    </root></mxGraphModel>"""
    compressor = zlib.compressobj(wbits=-15)
    payload = base64.b64encode(compressor.compress(quote(inner).encode()) + compressor.flush()).decode()
    ttl, _warnings = drawio_to_ttl(f'<mxfile><diagram id="x" name="p">{payload}</diagram></mxfile>')
    # "Train Model" must be classified as a process (verb wins over "model" noun)
    assert "ex:TrainModel a beam:Process" in ttl
    assert "beam:produce ex:Model" in ttl
    assert "beam:use ex:TrainingData" in ttl


def test_resource_to_resource_edge_is_skipped_with_warning() -> None:
    xml = """<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>
    <mxCell id="a" value="Dataset A" style="ellipse" vertex="1" parent="1"/>
    <mxCell id="b" value="Dataset B" style="ellipse" vertex="1" parent="1"/>
    <mxCell id="p" value="Process Step" vertex="1" parent="1"/>
    <mxCell id="e1" edge="1" source="a" target="b" parent="1"/>
    <mxCell id="e2" edge="1" source="a" target="p" parent="1"/>
    </root></mxGraphModel>"""
    ttl, warnings = drawio_to_ttl(xml)
    assert "beam:use ex:DatasetA" in ttl
    assert any("connects two resources" in w for w in warnings)


def test_invalid_xml_is_rejected() -> None:
    with pytest.raises(DrawioImportError):
        drawio_to_ttl("<not-a-diagram/>")
    with pytest.raises(DrawioImportError):
        drawio_to_ttl("no xml at all")
