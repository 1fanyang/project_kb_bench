# Benchmark Validation Report

## Verdict: PASS

- Rows: 100
- FAIL: 0
- WARN: 0

## Coverage

### project
- `nvdla`: 100

### layer
- `L1`: 20
- `L2`: 40
- `L3`: 40

### capability
- `build_sim_verif_flow`: 16
- `doc_code_cross_check`: 17
- `mechanism_trace`: 16
- `negative_insufficient_evidence`: 16
- `repo_structure_location`: 17
- `tests_debug_evidence`: 18

### answer_type
- `fact_check`: 20
- `location`: 21
- `mechanism`: 16
- `negative`: 8
- `procedure`: 17
- `synthesis`: 18

## Findings

- No findings.

## Sampled Cases

### nvdla-v1_2-L1-031

- Query: How does NVDLA handle low-precision inference support?
- Rewrite: How does NVDLA handle low-precision inference support?
- References:
  - `src:nvdla_sw:LowPrecision.md` `repo_sources/nvdla/sw/LowPrecision.md`
- Evidence:
  - `E1` `repo_sources/nvdla/sw/LowPrecision.md:16-18`: This section describes how to analyze each layer's tensor range and derive scaling, which fits the low-precision support topic.

```text
15: 
16: #### Analyze dynamic range of per-layer tensors and calculate scale factors using TensorRT
17: A calibration tool collects the dynamic range of the output tensor for each layer over a dataset of images. This dynamic range information can be used to calculate per-tensor scale factors. For NVDLA, calibration interface TensorRT is used to generate scale factors.
18: 
19: Refer to https://github.com/NVIDIA/TensorRT/tree/release/5.1/samples/opensource/sampleINT8 for sample application which explains how to use TensorRT to generate scales factors.
```


### nvdla-v1_2-L1-032

- Query: Where is the kernel mode driver documented in NVDLA?
- Rewrite: Where is the kernel mode driver documented in NVDLA?
- References:
  - `src:nvdla_sw:README.md` `repo_sources/nvdla/sw/README.md`
- Evidence:
  - `E1` `repo_sources/nvdla/sw/README.md:17-19`: The kernel mode driver is presented as part of the software documentation, which is the practical place to look for driver implementation details.

```text
16: 
17: ## Kernel Mode Driver
18: 
19: The kernel mode driver (KMD) is supported as a Linux out-of-tree kernel module.
20: It has been verified with Linux 4.13.3 on ARM64 and is expected to work
```


### nvdla-v1_2-L1-033

- Query: Which part of the implementation does this behavior belong to?
- Rewrite: Which part of the implementation does this behavior belong to?
- References:
  - `src:nvdla_sw:Roadmap.md` `repo_sources/nvdla/sw/Roadmap.md`
- Evidence:
  - `E1` `repo_sources/nvdla/sw/Roadmap.md:3-5`: The roadmap lists the DLA 1.3.0 milestone and a multibatch feature for FC layers, which anchors the relevant roadmap location.

```text
2: 
3: ### DLA 1.3.0
4: 
5: - HW Multibatch for FC layers
6: - Multi-input network support
```


### nvdla-v1_2-L1-034

- Query: How do I build the NVDLA documentation?
- Rewrite: How do I build the NVDLA documentation?
- References:
  - `src:nvdla_doc:README.txt` `repo_sources/nvdla/doc/README.txt`
- Evidence:
  - `E1` `repo_sources/nvdla/doc/README.txt:10-12`: The documentation section about building docs inside NVIDIA indicates an operational procedure rather than a code artifact.

```text
9: 
10: Building documentation inside of NVIDIA
11: ---------------------------------------
12: 
13: To build documentation on the NVIDIA farm, you need to first install Sphinx
```


### nvdla-v1_2-L1-035

- Query: What mechanism is this behavior using?
- Rewrite: What mechanism is this behavior using?
- References:
  - `src:nvdla_doc:doc/conduct.rst` `repo_sources/nvdla/doc/doc/conduct.rst`
- Evidence:
  - `E1` `repo_sources/nvdla/doc/doc/conduct.rst:83-85`: The conduct document has a dedicated standards section, so it is the right place for behavior and process rules.

```text
82: 
83: Attribution
84: ===========
85: 
86: This Code of Conduct is adapted from the `Contributor Covenant, version 1.4
```


### nvdla-v1_2-L1-036

- Query: What is the main index page for the NVDLA documentation?
- Rewrite: What is the main index page for the NVDLA documentation?
- References:
  - `src:nvdla_doc:doc/contents.rst` `repo_sources/nvdla/doc/doc/contents.rst`
- Evidence:
  - `E1` `repo_sources/nvdla/doc/doc/contents.rst:51-53`: The index page includes an 'Indices and tables' section, showing it is the documentation landing page rather than a feature page.

```text
50: 
51: Indices and tables
52: ==================
53: 
54: * :ref:`genindex`
```


### nvdla-v1_2-L1-037

- Query: Which part of the implementation does this behavior belong to?
- Rewrite: Which part of the implementation does this behavior belong to?
- References:
  - `src:nvdla_doc:doc/glossary.rst` `repo_sources/nvdla/doc/doc/glossary.rst`
- Evidence:
  - `E1` `repo_sources/nvdla/doc/doc/glossary.rst:2-4`: The glossary file is explicitly titled as the glossary and acronym reference, which places terminology definitions there.

```text
1: =====================
2: Glossary And Acronyms
3: =====================
4: 
5: 
```


### nvdla-v1_2-L1-038

- Query: Where is the NVDLA hardware manual?
- Rewrite: Where is the NVDLA hardware manual?
- References:
  - `src:nvdla_doc:doc/hw/contents.rst` `repo_sources/nvdla/doc/doc/hw/contents.rst`
- Evidence:
  - `E1` `repo_sources/nvdla/doc/doc/hw/contents.rst:1-3`: The hardware manual title indicates this is the main location for hardware documentation, so it answers where the manual lives.

```text
1: Hardware Manual
2: ===============
3: 
4: .. toctree::
```


### nvdla-v1_2-L1-039

- Query: Where is the NVDLA guide for in-memory data formats?
- Rewrite: Where is the NVDLA guide for in-memory data formats?
- References:
  - `src:nvdla_doc:doc/hw/format.rst` `repo_sources/nvdla/doc/doc/hw/format.rst`
- Evidence:
  - `E1` `repo_sources/nvdla/doc/doc/hw/format.rst:1145-1147`: The surrounding section on alignment tells you this file is about how memory data is represented and aligned, which matches the in-memory format topic.

```text
1144: 
1145: Alignment of Start Address and Stride
1146: -------------------------------------
1147: 
1148: Here is the conclusion of requirements of alignment:
```


### nvdla-v1_2-L1-040

- Query: Where is the introduction for the NVDLA v1 hardware architecture document?
- Rewrite: Where is the introduction for the NVDLA v1 hardware architecture document?
- References:
  - `src:nvdla_doc:doc/hw/v1/hwarch.rst` `repo_sources/nvdla/doc/doc/hw/v1/hwarch.rst`
- Evidence:
  - `E1` `repo_sources/nvdla/doc/doc/hw/v1/hwarch.rst:4-6`: The introduction section indicates this is the starting point for the hardware architecture document, even though the nearby anchor is an address-space subsection.

```text
3: 
4: Introduction
5: ============
6: 
7: The NVIDIA® Deep Learning Accelerator (NVDLA) is a configurable fixed function hardware accelerator targeting inference operations in deep learning applications. It provides full hardware acceleration for a convolutional neural network (CNN) by exposing individual building blocks that accelerate operations associated with each CNN layer (e.g., convolution, deconvolution, fully-connected, activation, pooling, local response normalization, etc.). Maintaining separate and independently configurable blocks means that the NVDLA can be sized appropriatley for many smaller applications where inferencing was previously not feasible due to cost, area, or power constraints. This modular architecture enables a highly configurable solution that readily scales to meet specific inferencing needs.
```
