import sys

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import array_join, collect_list, col, concat_ws, collect_set, size, when, lit, array
from pyspark.sql.types import ArrayType, StringType

from etl.jobs.util.dataframe_functions import join_left_dfs, join_dfs
from etl.jobs.util.id_assigner import add_id
from etl.workflow.config import PdcmConfig

column_names = ["pdcm_model_id", "external_model_id", "data_source", "histology", "data_available",
                "primary_site", "collection_site", "tumor_type", "patient_age", "patient_sex", "patient_ethnicity"]


def main(argv):
    """
    Creates a parquet file with provider type data.
    :param list argv: the list elements should be:
                    [1]: Parquet file path with raw molecular markers
                    [2]: Output file
    """
    model_parquet_path = argv[1]
    molecular_characterization_parquet_path = argv[2]
    molecular_characterization_type_parquet_path = argv[3]
    patient_sample_parquet_path = argv[4]
    patient_snapshot_parquet_path = argv[5]
    patient_parquet_path = argv[6]
    ethnicity_df_parquet_path = argv[7]
    xenograft_sample_parquet_path = argv[8]
    diagnosis_parquet_path = argv[9]
    tumour_type_parquet_path = argv[10]
    tissue_parquet_path = argv[11]
    mutation_marker_parquet_path = argv[12]
    mutation_measurement_data_parquet_path = argv[13]
    cna_data_parquet_path = argv[14]
    expression_data_parquet_path = argv[15]
    cytogenetics_data_parquet_path = argv[16]
    output_path = argv[17]

    spark = SparkSession.builder.getOrCreate()
    model_df = spark.read.parquet(model_parquet_path)
    molecular_characterization_df = spark.read.parquet(molecular_characterization_parquet_path)
    molecular_characterization_type_df = spark.read.parquet(molecular_characterization_type_parquet_path)
    patient_sample_df = spark.read.parquet(patient_sample_parquet_path)
    ethnicity_df = spark.read.parquet(ethnicity_df_parquet_path)
    patient_snapshot_df = spark.read.parquet(patient_snapshot_parquet_path)
    patient_df = spark.read.parquet(patient_parquet_path)
    xenograft_sample_df = spark.read.parquet(xenograft_sample_parquet_path)
    diagnosis_df = spark.read.parquet(diagnosis_parquet_path)
    tumour_type_df = spark.read.parquet(tumour_type_parquet_path)
    tissue_df = spark.read.parquet(tissue_parquet_path)
    mutation_marker_df = spark.read.parquet(mutation_marker_parquet_path)
    mutation_measurement_data_df = spark.read.parquet(mutation_measurement_data_parquet_path)
    cna_data_df = spark.read.parquet(cna_data_parquet_path)
    expression_data_df = spark.read.parquet(expression_data_parquet_path)
    cytogenetics_data_df = spark.read.parquet(cytogenetics_data_parquet_path)

    search_index_df = transform_search_index(model_df,
                                             patient_sample_df, patient_snapshot_df, patient_df, ethnicity_df,
                                             xenograft_sample_df,
                                             diagnosis_df,
                                             tumour_type_df, tissue_df, molecular_characterization_df,
                                             molecular_characterization_type_df, mutation_marker_df,
                                             mutation_measurement_data_df, cna_data_df, expression_data_df,
                                             cytogenetics_data_df)
    search_index_df.write.mode("overwrite").parquet(output_path)


def transform_search_index(model_df,
                           patient_sample_df, patient_snapshot_df, patient_df, ethnicity_df, xenograft_sample_df,
                           diagnosis_df,
                           tumour_type_df, tissue_df, molecular_characterization_df,
                           molecular_characterization_type_df, mutation_marker_df,
                           mutation_measurement_data_df, cna_data_df, expression_data_df,
                           cytogenetics_data_df) -> DataFrame:
    search_index_df = model_df.withColumnRenamed("id", "pdcm_model_id")

    # Adding diagnosis, primary_site, collection_site and tumour_type data to patient_sample
    diagnosis_df = diagnosis_df.withColumnRenamed("name", "histology")
    patient_sample_ext_df = join_left_dfs(patient_sample_df, diagnosis_df, "diagnosis_id", "id")

    primary_site_df = tissue_df.withColumnRenamed("name", "primary_site")
    patient_sample_ext_df = join_left_dfs(patient_sample_ext_df, primary_site_df, "primary_site_id", "id")

    collection_site_df = tissue_df.withColumnRenamed("name", "collection_site")
    patient_sample_ext_df = join_left_dfs(patient_sample_ext_df, collection_site_df, "collection_site_id", "id")

    # Adding age, sex and ethnicity to patient_sample
    patient_df = patient_df.withColumnRenamed("sex", "patient_sex")
    ethnicity_df = ethnicity_df.withColumnRenamed("name", "patient_ethnicity")
    patient_df = join_left_dfs(patient_df, ethnicity_df, "ethnicity_id", "id")
    patient_snapshot_df = join_left_dfs(patient_snapshot_df, patient_df, "patient_id", "id")
    patient_snapshot_df = patient_snapshot_df.withColumnRenamed("age_in_years_at_collection", "patient_age")
    patient_sample_ext_df = join_left_dfs(patient_sample_ext_df, patient_snapshot_df, "id", "sample_id")

    # Adding tumour_type name to patient_sample
    tumour_type_df = tumour_type_df.withColumnRenamed("name", "tumour_type")
    patient_sample_ext_df = join_left_dfs(patient_sample_ext_df, tumour_type_df, "tumour_type_id", "id")
    search_index_df = search_index_df.withColumn("temp_model_id", col("pdcm_model_id"))
    search_index_df = join_left_dfs(search_index_df, patient_sample_ext_df, "temp_model_id", "model_id")

    # Adding molecular data availability
    molecular_characterization_df = molecular_characterization_df.withColumnRenamed("id", "mol_char_id")
    molecular_characterization_type_df = molecular_characterization_type_df.withColumnRenamed("name",
                                                                                              "molecular_characterization_type_name")
    molecular_characterization_with_type_df = join_dfs(molecular_characterization_df,
                                                       molecular_characterization_type_df,
                                                       "molecular_characterization_type_id", "id", "inner")
    patient_sample_mol_char_df = join_dfs(patient_sample_df, molecular_characterization_with_type_df, "id",
                                          "patient_sample_id", "inner")
    patient_sample_mol_char_df = patient_sample_mol_char_df.select("model_id",
                                                                   "mol_char_id",
                                                                   "molecular_characterization_type_name").distinct()

    xenograft_sample_mol_char_df = join_dfs(xenograft_sample_df, molecular_characterization_with_type_df, "id",
                                            "xenograft_sample_id", "inner")
    xenograft_sample_mol_char_df = xenograft_sample_mol_char_df.select("model_id",
                                                                       "mol_char_id",
                                                                       "molecular_characterization_type_name").distinct()

    model_mol_char_type_df = patient_sample_mol_char_df.union(xenograft_sample_mol_char_df)

    model_mol_char_availability_df = model_mol_char_type_df.groupby("model_id").agg(
        array_join(collect_set("molecular_characterization_type_name"), "|").alias("dataset_available"))

    search_index_df = search_index_df.withColumn("temp_model_id", col("pdcm_model_id"))
    search_index_df = join_left_dfs(search_index_df, model_mol_char_availability_df, "temp_model_id", "model_id")

    # Adding mutation data availability by gene variant
    # Generate table model_id, mol_char_id, mol_char_type
    # Generate tables mol_char_id, tmp_symbol/gene_variant
    # Join left model_mol_char with mol_char_gene
    # then group by model, mol_char_type to collect the set of gene_variants and then pivot over mol_char_type
    mutation_marker_df = mutation_marker_df.select("id", "tmp_symbol", "amino_acid_change")
    mutation_marker_df = mutation_marker_df.withColumn("gene_variant",
                                                       when(col("amino_acid_change").isNotNull(),
                                                            concat_ws("/", "tmp_symbol",
                                                                      "amino_acid_change")).otherwise(col("tmp_symbol"))
                                                       )
    mutation_mol_char_df = mutation_measurement_data_df.select("mutation_marker_id", "molecular_characterization_id")
    mutation_mol_char_df = join_dfs(mutation_mol_char_df, mutation_marker_df, "mutation_marker_id", "id", "inner")
    mutation_mol_char_df = mutation_mol_char_df.select("molecular_characterization_id", "gene_variant")
    # Adding CNA data availability by gene
    cna_data_df = cna_data_df.withColumnRenamed("tmp_symbol", "gene_variant")
    cna_data_df = cna_data_df.select("molecular_characterization_id", "gene_variant").distinct()

    # Adding expression data availability by gene
    expression_data_df = expression_data_df.withColumnRenamed("tmp_symbol", "gene_variant")
    expression_data_df = expression_data_df.select("molecular_characterization_id", "gene_variant").distinct()

    # Adding cytogenetics data availability by gene and result
    cytogenetics_data_df = cytogenetics_data_df.withColumnRenamed("tmp_symbol", "gene_variant")
    cytogenetics_data_df = cytogenetics_data_df.select("molecular_characterization_id", "gene_variant").distinct()

    mol_gene_df = mutation_mol_char_df.union(cna_data_df).union(expression_data_df).union(cytogenetics_data_df)

    model_mol_char_type_gene_df = join_dfs(model_mol_char_type_df, mol_gene_df, "mol_char_id",
                                           "molecular_characterization_id", "inner")

    model_mol_char_availability_by_gene_df = model_mol_char_type_gene_df.groupby("model_id").pivot(
        "molecular_characterization_type_name").agg(collect_set("gene_variant"))
    molecular_data_col_map = {
        "copy number alteration": "makers_with_cna_data",
        "mutation": "makers_with_mutation_data",
        "expression": "makers_with_expression_data",
        "cytogenetics": "makers_with_cytogenetics_data"
    }

    for category, col_name in molecular_data_col_map.items():
        if category in model_mol_char_availability_by_gene_df.columns:
            model_mol_char_availability_by_gene_df = model_mol_char_availability_by_gene_df.withColumnRenamed(category,
                                                                                                              col_name)
        else:
            model_mol_char_availability_by_gene_df = model_mol_char_availability_by_gene_df.withColumn(col_name,
                                                                                                       array().astype(
                                                                                                           ArrayType(
                                                                                                               StringType())))

    search_index_df = search_index_df.withColumn("temp_model_id", col("pdcm_model_id"))
    search_index_df = join_left_dfs(search_index_df, model_mol_char_availability_by_gene_df, "temp_model_id",
                                    "model_id")
    search_index_df = search_index_df.select("pdcm_model_id",
                                             "external_model_id",
                                             "data_source",
                                             "histology",
                                             "dataset_available",
                                             "primary_site",
                                             "collection_site",
                                             "tumour_type",
                                             "patient_age",
                                             "patient_sex",
                                             "patient_ethnicity",
                                             "makers_with_cna_data",
                                             "makers_with_mutation_data",
                                             "makers_with_expression_data",
                                             "makers_with_cytogenetics_data")
    return search_index_df


if __name__ == "__main__":
    sys.exit(main(sys.argv))
