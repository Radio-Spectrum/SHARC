---
sidebar_position: 1
---

# Earth Exploration Satellite Service (EESS)

---

## Earth Exploration Satellite Service (EESS active and passive)

The **Earth Exploration Satellite Service** is a radiocommunication service that 
employs satellites to gather environmetal data, facilitating analysis and monitoring 
of the Earth's surface and atmosphere. The systme is essential in land-use studies, oceanography, 
disaster and environmental management. The implemented spacial system is indispensable for research
and management actities in atmospherical context.

### Overview

EESS system uses satellites equiped with advanced sensors that capture a wide range of that, such as 
high-resolution imagery to atmospheric reading, covering various frequencies from visible light to microwave bands.
All the captured data are transmitted to ground stations, named as **Earth Stations**.

### Spectrum Use and Technical Standards

The **International Telecommunication Union (ITU)** regularizes the use of these bands to ensure compatibility with other
radiocommunication services. According to [ITU-R RS.1861 Typical technical and operational characteristics of Earth exploration-satellite service (passive) systems using allocations between 1.4 and 275 GHz](https://extranet.itu.int/brdocsearch/R-REC/R-REC-RS/R-REC-RS.1861/R-REC-RS.1861-0-201001-I/R-REC-RS.1861-0-201001-I!!PDF-E.pdf) 
and the well known [Handbook of Earth Exploration Satellite Service](https://www.itu.int/dms_pub/itu-r/opb/hdb/R-HDB-56-2011-PDF-E.pdf).

### Types of EESS: Active and Passive

EESS is categorized into two types based on data collection methods:

#### EESS Active:

- **Data Collection Method**: EESS (Active) satellites actively emit signals toward the Earth’s surface and measure the reflected or backscattered signals. This approach allows the satellite to gather data on a variety of surface and atmospheric conditions.
- **Primary Instruments**: Active EESS systems often use radar, lidar, and altimeters to send pulses and then measure their return. Radar, for example, can penetrate through clouds, making it effective for consistent imaging, regardless of weather conditions.
- **Applications**:
  - **Topographic Mapping**: Radar altimeters on active EESS satellites can create high-resolution maps of Earth’s surface topography.
  - **Sea Ice and Forest Monitoring**: Active sensing is useful for tracking changes in ice coverage and forest density.
  - **Soil Moisture and Ocean Salinity**: Radar instruments help monitor soil moisture content and ocean salinity levels, which are critical for agriculture and climate studies.
- **Spectrum Needs**: EESS (Active) often operates in the microwave spectrum (e.g., 1–40 GHz). The ITU allocates specific frequency bands for active systems to avoid interference with other services and to support high-resolution data collection.

#### EESS Passive:

- **Data Collection Method**: EESS (Passive) satellites do not emit any signals but instead detect natural emissions, including thermal and reflected sunlight from the Earth's surface and atmosphere. They passively receive this energy across a wide range of frequencies, capturing detailed information about natural emissions.
- **Primary Instruments**: Passive EESS systems rely on sensors like radiometers, spectrometers, and radiotelescopes, which measure radiation across multiple bands from visible to microwave. These sensors are particularly sensitive and require interference-free channels.
- **Applications**:
  - **Atmospheric and Climate Monitoring**: Passive sensors measure atmospheric temperatures, trace gases, and water vapor levels, which are essential for weather prediction and climate modeling.
  - **Ocean and Ice Studies**: By detecting the natural microwave emissions of the ocean and ice, passive sensors help monitor sea surface temperature, ice thickness, and extent.
  - **Vegetation and Soil Analysis**: These sensors detect soil moisture, vegetation health, and drought conditions, aiding in agriculture and environmental management.
- **Spectrum Needs**: Passive EESS requires strict protection in specific frequency bands where natural emissions are observed, as any interference can disrupt these sensitive measurements. The ITU has designated interference-free bands for passive EESS to preserve the accuracy and reliability of the collected data.

### Summary of the differences of two types data collection

| Feature             | EESS (Active)                               | EESS (Passive)                              |
|---------------------|---------------------------------------------|---------------------------------------------|
| **Signal Type**     | Emits signals and measures reflections      | Detects natural emissions only              |
| **Instruments**     | Radar, lidar, altimeters                    | Radiometers, spectrometers, radiotelescopes |
| **Key Applications**| Topography, soil moisture, ocean salinity   | Atmospheric composition, sea surface temp   |
| **Weather Dependence** | Not affected by weather (e.g., radar penetrates clouds) | Limited to clear weather for some wavelengths |
| **Spectrum Needs**  | Specific microwave bands, with lower risk of interference | Strictly interference-free in designated bands |

## Guidelines and Further Reading

For more in-depth information, refer to:

- [Handbook of Earth Exploration Satellite Service](https://www.itu.int/dms_pub/itu-r/opb/hdb/R-HDB-56-2011-PDF-E.pdf)

---
