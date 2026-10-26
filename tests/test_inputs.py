import csv
import json

import pytest
from openpyxl import Workbook
from pydantic import ValidationError

from backend.app.schemas import FilingMetadata, RateRow
from backend.app.tools.inputs import InputValidationError, load_filing, load_rates, validate_records


def valid_record():
    return dict(segment_id="A", current_base_rate="100", proposed_base_rate="105",
                current_rating_factor="1", proposed_rating_factor="1")


@pytest.mark.parametrize("field", ["current_base_rate", "proposed_base_rate", "current_rating_factor", "proposed_rating_factor"])
@pytest.mark.parametrize("value", [None, "", "0", "-1", "NaN", "Infinity", "abc", True])
def test_invalid_rate_inputs(field, value):
    with pytest.raises(InputValidationError):
        validate_records([(2, {**valid_record(), field: value})])


@pytest.mark.parametrize("field", ["exposure", "current_premium", "reported_change_pct"])
@pytest.mark.parametrize("value", ["NaN", "-Infinity", "abc", True])
def test_invalid_optional_numeric_inputs(field, value):
    with pytest.raises(InputValidationError):
        validate_records([(2, {**valid_record(), field: value})])


def test_duplicate_segments_rejected():
    with pytest.raises(InputValidationError, match="Duplicate segment ID"):
        validate_records([(2, valid_record()), (3, valid_record())])


def test_no_rows_rejected():
    with pytest.raises(InputValidationError, match="At least one"):
        validate_records([])


def test_too_many_rows_rejected():
    with pytest.raises(InputValidationError, match="5000"):
        validate_records([(i+2, valid_record()) for i in range(5001)])


def test_missing_optional_weights_accepted():
    rows, sources = validate_records([(2, valid_record())])
    assert rows[0].exposure is None
    assert rows[0].current_premium is None
    assert sources[0].row_number == 2


@pytest.mark.parametrize("header", ["segment_id,segment_id", "segment_id,current_base_rate", ""])
def test_bad_csv_header(tmp_path, header):
    path = tmp_path / "rates.csv"
    path.write_text(header + "\n", encoding="utf-8")
    with pytest.raises(InputValidationError):
        load_rates(path)


def test_unknown_column_rejected(tmp_path):
    record = {**valid_record(), "exposures_typo": "10"}
    path = tmp_path / "rates.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(record))
        writer.writeheader()
        writer.writerow(record)
    with pytest.raises(InputValidationError, match="Unknown columns"):
        load_rates(path)


def test_csv_extra_cell_rejected(tmp_path):
    path = tmp_path / "rates.csv"
    path.write_text(",".join(valid_record()) + "\n" + ",".join(valid_record().values()) + ",extra\n", encoding="utf-8")
    with pytest.raises(InputValidationError, match="Row width"):
        load_rates(path)


def test_csv_physical_source_rows(tmp_path):
    path = tmp_path / "rates.csv"
    path.write_text(",".join(valid_record()) + "\n\n" + ",".join(valid_record().values()) + "\n", encoding="utf-8")
    _, sources = load_rates(path)
    assert sources[0].row_number == 3


def test_oversize_file(tmp_path):
    path = tmp_path / "rates.csv"
    path.write_bytes(b"x" * 2_000_001)
    with pytest.raises(InputValidationError, match="2 MB"):
        load_rates(path)


@pytest.mark.parametrize("problem", ["formula", "missing_sheet", "missing_segment"])
def test_xlsx_validation(tmp_path, problem):
    path = tmp_path / "rates.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "other" if problem == "missing_sheet" else "rates"
    record = valid_record()
    if problem == "formula":
        record["proposed_base_rate"] = "=100*1.05"
    if problem == "missing_segment":
        record["segment_id"] = None
    sheet.append(list(record))
    sheet.append(list(record.values()))
    workbook.save(path)
    workbook.close()
    with pytest.raises(InputValidationError):
        load_rates(path)


def test_corrupt_xlsx(tmp_path):
    path = tmp_path / "rates.xlsx"
    path.write_text("not an xlsx", encoding="utf-8")
    with pytest.raises(InputValidationError, match="Invalid XLSX"):
        load_rates(path)


def test_real_numeric_xlsx_cells(tmp_path):
    path = tmp_path / "rates.xlsx"
    record = valid_record()
    record["current_base_rate"] = 100.25
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "rates"
    sheet.append(list(record))
    sheet.append(list(record.values()))
    workbook.save(path)
    workbook.close()
    rows, sources = load_rates(path)
    assert str(rows[0].current_base_rate) == "100.25"
    assert sources[0].sheet == "rates"


def test_input_error_omits_raw_value():
    with pytest.raises(InputValidationError) as error:
        validate_records([(2, {**valid_record(), "current_base_rate": "SENSITIVE_DUMMY_TEXT"})])
    assert "SENSITIVE_DUMMY_TEXT" not in str(error.value)


@pytest.mark.parametrize("state,lob", [("NY", "Personal Auto"), ("CT", "Homeowners")])
def test_scope_enforced(examples, state, lob):
    data = json.loads((examples / "clean" / "filing.json").read_text())
    data.update(state=state, line_of_business=lob)
    with pytest.raises(ValidationError):
        FilingMetadata.model_validate(data)


def test_unknown_claimed_weighting_basis_rejected(examples):
    data = json.loads((examples / "clean" / "filing.json").read_text())
    data["claimed_overall_basis"] = "whatever_is_available"
    with pytest.raises(ValidationError):
        FilingMetadata.model_validate(data)


def test_document_inventory_requires_actual_text(examples):
    data = json.loads((examples / "clean" / "filing.json").read_text())
    data["documents"][0]["text"] = ""
    with pytest.raises(ValidationError):
        FilingMetadata.model_validate(data)


def test_duplicate_document_ids_rejected(examples):
    data = json.loads((examples / "clean" / "filing.json").read_text())
    data["documents"][1]["document_id"] = data["documents"][0]["document_id"]
    with pytest.raises(ValidationError):
        FilingMetadata.model_validate(data)


def test_rates_path_allowlist(examples):
    with pytest.raises(InputValidationError, match="Choose rates"):
        load_filing(examples / "clean", "../../../evaluation/answer_key.json")


def test_precision_limit_rejected():
    with pytest.raises(ValidationError):
        RateRow.model_validate({**valid_record(), "current_rating_factor": "0.123456789"})


def test_overlong_narrative_rejected(examples, tmp_path):
    for name in ("rates.csv", "filing.json"):
        (tmp_path / name).write_bytes((examples / "clean" / name).read_bytes())
    (tmp_path / "narrative.md").write_text("x" * 20001, encoding="utf-8")
    with pytest.raises(InputValidationError):
        load_filing(tmp_path)
