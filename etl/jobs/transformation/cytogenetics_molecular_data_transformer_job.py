import sys

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import lit

from etl.jobs.util.id_assigner import add_id


def main(argv):
    """
    Creates a parquet file with provider type data.
    :param list argv: the list elements should be:
                    [1]: Parquet file path with raw cytogenetics data
                    [2]: Output file
    """
    molecular_characterization_path = argv[1]
    raw_cytogenetics_parquet_path = argv[2]

    output_path = argv[3]

    spark = SparkSession.builder.getOrCreate()
    molecular_characterization_df = spark.read.parquet(molecular_characterization_path)
    raw_cytogenetics_df = spark.read.parquet(raw_cytogenetics_parquet_path)

    cytogenetics_molecular_data_df = transform_cytogenetics_molecular_data(
        molecular_characterization_df, raw_cytogenetics_df)
    cytogenetics_molecular_data_df.write.mode("overwrite").parquet(output_path)


def transform_cytogenetics_molecular_data(
        molecular_characterization_df: DataFrame, raw_cytogenetics_df: DataFrame) -> DataFrame:
    cytogenetics_df = get_cytogenetics_df(raw_cytogenetics_df)
    cytogenetics_df = set_fk_molecular_characterization(cytogenetics_df, molecular_characterization_df)
    cytogenetics_df = add_id(cytogenetics_df, "id")
    # Temporary use column tmp_symbol instead of Gene_marker_id while Gene Marker table has data
    cytogenetics_df = cytogenetics_df.withColumnRenamed("symbol", "tmp_symbol")
    cytogenetics_df = get_expected_columns(cytogenetics_df)
    return cytogenetics_df


def get_cytogenetics_df(raw_cytogenetics_df: DataFrame) -> DataFrame:
    return raw_cytogenetics_df.select(
        "sample_id",
        "sample_origin",
        lit("cytogenetics").alias("molchar_type"),
        "marker_status",
        "symbol",
        "platform",
        "essential_or_additional_marker").drop_duplicates()


def set_fk_molecular_characterization(cytogenetics_df: DataFrame, molecular_characterization_df: DataFrame) -> DataFrame:
    molecular_characterization_df = molecular_characterization_df.withColumnRenamed(
        "id", "molecular_characterization_id")
    cytogenetics_df_patient_sample_df = cytogenetics_df.where("sample_origin = 'patient'")
    cytogenetics_df_patient_sample_df = cytogenetics_df_patient_sample_df.drop("sample_origin")
    cytogenetics_df_patient_sample_df = cytogenetics_df_patient_sample_df.withColumnRenamed(
        "sample_id", "external_patient_sample_id")

    cytogenetics_df_patient_sample_df = cytogenetics_df_patient_sample_df.join(
        molecular_characterization_df, on=['molchar_type', 'platform', 'external_patient_sample_id'])

    cytogenetics_df_xenograft_sample_df = cytogenetics_df.where("sample_origin = 'xenograft'")
    cytogenetics_df_xenograft_sample_df = cytogenetics_df_xenograft_sample_df.drop("sample_origin")
    cytogenetics_df_xenograft_sample_df = cytogenetics_df_xenograft_sample_df.withColumnRenamed(
        "sample_id", "external_xenograft_sample_id")

    cytogenetics_xenograft_sample_df = cytogenetics_df_xenograft_sample_df.join(
        molecular_characterization_df, on=['molchar_type', 'platform', 'external_xenograft_sample_id'])

    cytogenetics_df = cytogenetics_df_patient_sample_df.union(cytogenetics_xenograft_sample_df)
    return cytogenetics_df


def get_expected_columns(ethnicity_df: DataFrame) -> DataFrame:
    return ethnicity_df.select(
        "id", "marker_status", "essential_or_additional_marker", "tmp_symbol", "molecular_characterization_id")


if __name__ == "__main__":
    sys.exit(main(sys.argv))