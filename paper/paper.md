---
title: 'OpenTTDLab: A Python framework for reproducible experiments using OpenTTD'
tags:
  - Python
authors:
  - name: Michal Charemza
    orcid: 0009-0009-1002-1036
    affiliation: 1
  - name: J. Michael Herrmann
    orcid: 0000-0001-6255-3944
    affiliation: 1
affiliations:
 - name: University of Edinburgh, United Kingdom
   index: 1
   ror: 01nrxwf90
date: 8 December 2024
bibliography: paper.bib

---

# Summary

![OpenTTDLab](openttdlab-logo.pdf){height="100pt"}

OpenTTD [@openttdteam2004openttd] is a business simulation game originally created for recreation, where one or more human players build companies through constructing and using a transportation network to transport passengers and goods. OpenTTD can be extended by allowing autonomous so-called AI players, and it is by leveraging this capability that OpenTTDLab converts OpenTTD from a game into a system for researching algorithms and their effects on companies and supply chains, and helps to ensure the results of such research are reproducible.

# Statement of need

OpenTTD is remarkably flexible: by leveraging the OpenTTD AI system it has been already successfully used as a tool to research algorithms including artificial intelligence (AI), machine learning (ML), and anomaly detection algorithms [@beuneker2019autonomous; @bijlsma2014evolving; @konijnendijk2015mcts; @lakomy2020railroad; @rios2009trains; @wisniewski2011artificial; @volna2017fuzzy]. However, OpenTTD does not include the capability to easily repeat experiments over ranges of configuration--unsurprising since it is designed to be a game--and this fact results in much of the existing research not being able to be reproduced [@charemza2024reusable]. OpenTTD addresses this by providing a framework through which experiments similar to those of the existing literature can be easily run by writing and running Python code, and encourages such code to be shared so future researchers can easily reproduce any results.

# Acknowledgments

OpenTTDLab could not have been created without incredible work of all the [contributors to OpenTTD, its dependencies, and precursors](https://github.com/OpenTTD/OpenTTD/blob/master/CREDITS.md).

# References
