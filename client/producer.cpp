/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/*
 * Copyright (c) 2016-2025, Regents of the University of California,
 *                          Colorado State University,
 *                          University Pierre & Marie Curie, Sorbonne University.
 *
 * This file is part of ndn-tools (Named Data Networking Essential Tools).
 * See AUTHORS.md for complete list of ndn-tools authors and contributors.
 *
 * ndn-tools is free software: you can redistribute it and/or modify it under the terms
 * of the GNU General Public License as published by the Free Software Foundation,
 * either version 3 of the License, or (at your option) any later version.
 *
 * ndn-tools is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
 * without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
 * PURPOSE.  See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along with
 * ndn-tools, e.g., in COPYING.md file.  If not, see <http://www.gnu.org/licenses/>.
 *
 * See AUTHORS.md for complete list of ndn-cxx authors and contributors.
 *
 * @author Wentao Shang
 * @author Steve DiBenedetto
 * @author Andrea Tosatto
 * @author Davide Pesavento
 * @author Klaus Schneider
 * @author Chavoosh Ghasemi
 */

#include "producer.hpp"

#include <ndn-cxx/metadata-object.hpp>
#include <ndn-cxx/util/segmenter.hpp>

#include <iostream>
#include <fstream>
#include <filesystem>

namespace ndn::serve {

Producer::Producer(const Name& prefix, Face& face, KeyChain& keyChain, const std::string& dataDir, std::ofstream& logFile,
                   const Options& opts)
  : m_prefix(prefix)
  , m_dataDir(dataDir)
  , m_face(face)
  , m_keyChain(keyChain)
  , m_options(opts)
  , m_logFile(logFile)
{
  if (!m_options.isQuiet) {
    m_logFile << "Producer initialized with prefix: " << m_prefix << " and data directory: " << m_dataDir << std::endl;
  }

  // register m_prefix without Interest handler
  m_face.registerPrefix(m_prefix, nullptr, [this] (const Name& prefix, const auto& reason) {
    m_logFile << "ERROR: Failed to register prefix '" << prefix << "' (" << reason << ")" << std::endl;
    m_face.shutdown();
  });

  // match Interests for specific files: /prefix/<filename>/<version>/<segment>
  face.setInterestFilter(Name(m_prefix), [this] (const auto&, const auto& interest) {
    processSegmentInterest(interest);
  });

  // match discovery Interests
  auto discoveryName = MetadataObject::makeDiscoveryInterest(m_prefix).getName();
  face.setInterestFilter(discoveryName, [this] (const auto&, const auto& interest) {
    processDiscoveryInterest(interest);
  });

  if (!m_options.isQuiet) {
    m_logFile << "Producer ready to serve files from directory: " << m_dataDir << std::endl;
  }
}

void
Producer::run()
{
  m_face.processEvents(0_ms, true);
}

void
Producer::processDiscoveryInterest(const Interest& interest)
{
  if (m_options.isVerbose)
    m_logFile << "Discovery Interest: " << interest << std::endl;

  if (!interest.getCanBePrefix()) {
    if (m_options.isVerbose) {
      m_logFile << "Discovery Interest lacks CanBePrefix, sending Nack" << std::endl;
    }
    m_face.put(lp::Nack(interest));
    return;
  }

  // Extract filename from discovery interest if present
  std::string filename = extractFilenameFromInterest(interest);
  if (!filename.empty()) {
    std::lock_guard<std::mutex> lock(m_storeMutex);
    auto it = m_fileStores.find(filename);
    if (it != m_fileStores.end()) {
      MetadataObject mobject;
      mobject.setVersionedName(it->second.versionedPrefix);
      
      auto mdata = mobject.makeData(interest.getName(), m_keyChain, m_options.signingInfo);
      
      if (m_options.isVerbose)
        m_logFile << "Sending metadata for " << filename << ": " << mdata << std::endl;
      
      m_face.put(mdata);
      return;
    }
  }

  // General discovery response
  m_face.put(lp::Nack(interest));
}

void
Producer::processSegmentInterest(const Interest& interest)
{
  if (m_options.isVerbose)
    m_logFile << "Interest: " << interest << std::endl;

  const Name& name = interest.getName();
  
  // Extract filename from interest: /prefix/<filename>/...
  std::string filename = extractFilenameFromInterest(interest);
  if (filename.empty()) {
    if (m_options.isVerbose) {
      m_logFile << "Cannot extract filename from interest, sending Nack" << std::endl;
    }
    m_face.put(lp::Nack(interest));
    return;
  }

  // Load file if not already loaded
  if (!loadFileIntoStore(filename)) {
    if (m_options.isVerbose) {
      m_logFile << "Failed to load file " << filename << ", sending Nack" << std::endl;
    }
    m_face.put(lp::Nack(interest));
    return;
  }

  std::lock_guard<std::mutex> lock(m_storeMutex);
  auto it = m_fileStores.find(filename);
  if (it == m_fileStores.end()) {
    if (m_options.isVerbose) {
      m_logFile << "File " << filename << " not found in store, sending Nack" << std::endl;
    }
    m_face.put(lp::Nack(interest));
    return;
  }

  const auto& fileStore = it->second;
  const auto& versionedPrefix = fileStore.versionedPrefix;
  const auto& segments = fileStore.segments;

  std::shared_ptr<Data> data;

  if (name.size() == versionedPrefix.size() + 1 && name[-1].isSegment()) {
    const auto segmentNo = static_cast<size_t>(interest.getName()[-1].toSegment());
    // specific segment retrieval
    if (segmentNo < segments.size()) {
      data = segments[segmentNo];
    }
  }
  else if (!segments.empty() && interest.matchesData(*segments[0])) {
    // unspecified version or segment number, return first segment
    data = segments[0];
  }

  if (data != nullptr) {
    if (m_options.isVerbose) {
      m_logFile << "Data: " << *data << std::endl;
    }
    m_face.put(*data);
  }
  else {
    if (m_options.isVerbose) {
      m_logFile << "Interest cannot be satisfied, sending Nack" << std::endl;
    }
    m_face.put(lp::Nack(interest));
  }
}

bool
Producer::loadFileIntoStore(const std::string& filename)
{
  std::lock_guard<std::mutex> lock(m_storeMutex);
  
  // Check if already loaded
  if (m_fileStores.find(filename) != m_fileStores.end()) {
    return true;
  }

  // Construct file path
  std::filesystem::path filePath = std::filesystem::path(m_dataDir) / filename;
  
  if (!std::filesystem::exists(filePath)) {
    m_logFile << "File not found: " << filePath << std::endl;
    return false;
  }

  // Open file
  std::ifstream file(filePath, std::ios::binary);
  if (!file.is_open()) {
    m_logFile << "Failed to open file: " << filePath << std::endl;
    return false;
  }

  // Create versioned prefix: /prefix/filename/version
  Name versionedPrefix;
  if (m_options.disableVersionDiscovery) {
    versionedPrefix = Name(m_prefix).append(filename);
  } else {
    versionedPrefix = Name(m_prefix).append(filename).appendVersion();
  }

  if (!m_options.isQuiet) {
    m_logFile << "Loading file: " << filename << " with prefix: " << versionedPrefix << std::endl;
  }

  // Segment the file
  auto start = std::chrono::steady_clock::now();

  Segmenter segmenter(m_keyChain, m_options.signingInfo);
  auto segments = segmenter.segment(file, versionedPrefix, m_options.maxSegmentSize, m_options.freshnessPeriod);
 
  auto end = std::chrono::steady_clock::now();
  m_segmentationTime = std::chrono::duration_cast<std::chrono::microseconds>(end - start);
  if (!m_options.isQuiet) {
    m_logFile << "Segmenting took " << m_segmentationTime.count() << " μs" << std::endl;
  }

  // Debug: log how many segments were produced
  if (m_options.isVerbose) {
    m_logFile << "Segmenter returned " << segments.size() << " segments" << std::endl;
  }
  if (!segments.empty()) {
    if (!m_options.isQuiet) {
      m_logFile << "First segment name (preview): " << segments[0]->getName() << std::endl;
    }
  } else {
    m_logFile << "ERROR: No segments produced by Segmenter for file " << filePath << std::endl;
    m_logFile << " - Check KeyChain/signingInfo and ndn-cxx Segmenter behavior." << std::endl;
    file.close();
    return false; // prevent storing empty segments
  }

  // Get file size
  file.seekg(0, std::ios::end);
  size_t fileSize = file.tellg();
  file.close();

  // Store in map
  FileStore store;
  store.segments = std::move(segments);
  store.versionedPrefix = versionedPrefix;
  store.filename = filename;
  store.totalSize = fileSize;

  m_fileStores[filename] = std::move(store);

  if (!m_options.isQuiet) {
    m_logFile << "Successfully loaded " << filename << " with " << m_fileStores[filename].segments.size() 
              << " segments, total size: " << fileSize << " bytes" << std::endl;
  }

  return true;
}

std::string
Producer::extractFilenameFromInterest(const Interest& interest)
{
  const Name& name = interest.getName();
  
  // Expected format: /prefix/<filename>/...
  if (name.size() <= m_prefix.size()) {
    return "";
  }

  // Check if interest name starts with our prefix
  if (!m_prefix.isPrefixOf(name)) {
    return "";
  }

  // Extract filename (component right after prefix)
  return name.get(m_prefix.size()).toUri();
}
} // namespace ndn::serve