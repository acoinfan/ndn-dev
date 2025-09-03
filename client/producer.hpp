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
 */

#ifndef NDN_TOOLS_SERVE_PRODUCER_HPP
#define NDN_TOOLS_SERVE_PRODUCER_HPP

#include "core/common.hpp"

#include <ndn-cxx/face.hpp>
#include <ndn-cxx/security/key-chain.hpp>

#include <vector>
#include <unordered_map>
#include <mutex>

namespace ndn::serve {

/**
 * @brief Segmented & versioned data publisher.
 *
 * Publishes data from files in a directory as `/prefix/<filename>/<version>/<segment number>`.
 * Unless another value is provided, the current time is used as the version number.
 * Supports serving multiple files dynamically from a directory.
 */
class Producer : noncopyable
{
public:
  struct Options
  {
    security::SigningInfo signingInfo;
    time::milliseconds freshnessPeriod = 10_s;
    size_t maxSegmentSize = 8000;
    bool isQuiet = false;
    bool isVerbose = false;
    bool wantShowVersion = true;
    bool disableVersionDiscovery = true;
  };

  /**
   * @brief Create the producer.
   * @param prefix prefix used to publish data; 
   * @param dataDir directory containing files to serve
   */
  Producer(const Name& prefix, Face& face, KeyChain& keyChain, const std::string& dataDir, std::ofstream& logFile,
           const Options& opts);

  /**
   * @brief Run the producer.
   */
  void
  run();

  /**
   * @brief Get segmentation time.
   */
  inline std::chrono::microseconds
  getSegmentationTime() const { return m_segmentationTime; };

private:
  struct FileStore {
    std::vector<std::shared_ptr<Data>> segments;
    Name versionedPrefix;
    std::string filename;
    size_t totalSize;
  };

  /**
   * @brief Respond with a metadata packet containing the versioned content name.
   */
  void
  processDiscoveryInterest(const Interest& interest);

  /**
   * @brief Respond with the requested segment of content.
   */
  void
  processSegmentInterest(const Interest& interest);

  /**
   * @brief Load a file into the store if not already loaded
   */
  bool
  loadFileIntoStore(const std::string& filename);

  /**
   * @brief Extract filename from interest name
   */
  std::string
  extractFilenameFromInterest(const Interest& interest);

PUBLIC_WITH_TESTS_ELSE_PRIVATE:
  std::unordered_map<std::string, FileStore> m_fileStores;
  std::mutex m_storeMutex;

private:
  Name m_prefix;
  std::string m_dataDir;
  Face& m_face;
  KeyChain& m_keyChain;
  const Options m_options;
  std::ofstream& m_logFile;
  std::chrono::microseconds m_segmentationTime{0};
};

} // namespace ndn::serve

#endif // NDN_TOOLS_SERVE_PRODUCER_HPP