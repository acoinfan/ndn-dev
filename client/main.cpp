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
 * @author Weiwei Liu
 * @author Klaus Schneider
 * @author Chavoosh Ghasemi
 */

#include "async-consumer.hpp"
#include "async-producer.hpp"
#include "discover-version.hpp"
#include "pipeline-interests-aimd.hpp"
#include "pipeline-interests-cubic.hpp"
#include "pipeline-interests-fixed.hpp"
#include "statistics-collector.hpp"
#include "core/version.hpp"

#include <ndn-cxx/security/validator-null.hpp>
#include <ndn-cxx/util/rtt-estimator.hpp>
#include <ndn-cxx/transport/unix-transport.hpp>

#include <boost/program_options/options_description.hpp>
#include <boost/program_options/parsers.hpp>
#include <boost/program_options/variables_map.hpp>

#include <fstream>
#include <iostream>
#include <cstdio>

#include "inipp.h"

namespace ndn::get
{

  namespace po = boost::program_options;

  // declaration of helper functions
  static bool get_bool(std::string const &value, std::string const &clientPrefix, std::ofstream &os, std::string const &errorMsg = "");

  static int get_int(std::string const &value, std::string const &clientPrefix, std::ofstream &os, std::string const &errorMsg = "");

  static double get_double(std::string const &value, std::string const &clientPrefix, std::ofstream &os, std::string const &errorMsg = "");

  static long get_long(std::string const &value, std::string const &clientPrefix, std::ofstream &os, std::string const &errorMsg = "");
  // end of declaration

  static int main(int argc, char *argv[])
  {
    // Initialize options and variables
    Options consumerOptions;
    AsyncConsumerOptions asyncConsumerOptions;

    ndn::chunks::Producer::Options producerOptions;
    util::RttEstimator::Options rttEstOptions;

    std::string fileName, nameConv, pipelineType, configPath, fileDir, signingInfo; // fileName is the file to be fetched and sent
    int id, totalNodes;
    std::string cwndPath, rttPath, signalFile = "/tmp/ndn/all.ok"; // signal file path
    const std::string programName(argv[0]);

    // Analyse command line options
    po::options_description basicDesc("Basic Options");
    basicDesc.add_options()
    ("help,h", "print this help message and exit")
    ("config,c", po::value<std::string>(&configPath),
                    "path to the configuration file")
    ("filename,f", po::value<std::string>(&fileName),
                    "file name of the requested content")
    ("id,i", po::value<int>(&id),
                    "the unique ID of this consumer node")
    ("nodes,n", po::value<int>(&totalNodes),
                    "the total number of consumer nodes in the experiment")
    ("directory,d", po::value<std::string>(&fileDir)->required(),
                    "Directory of files to store and send (absolute path)");

    po::variables_map vm;
    po::store(po::command_line_parser(argc, argv).options(basicDesc).run(), vm);
    po::notify(vm);

    if (vm.count("help") > 0)
    {
      std::cout << "Usage: " << programName << " [options]\n";
      std::cout << basicDesc;
      return 0;
    }

    std::string clientPrefix = "client" + std::to_string(id);
    std::ofstream logFile("/tmp/ndn/" + clientPrefix + ".log");

    if (vm.count("config") == 0)
    {
      logFile << clientPrefix << " ERROR: --config is required\n";
      return 2;
    }

    if (vm.count("filename") == 0)
    {
      logFile << clientPrefix << " ERROR: --filename is required\n";
      return 2;
    }

    if (vm.count("id") == 0)
    {
      logFile << clientPrefix << " ERROR: --id is required\n";
      return 2;
    }

    if (vm.count("nodes") == 0)
    {
      logFile << clientPrefix << " ERROR: --nodes is required\n";
      return 2;
    }

    if (vm.count("directory") == 0)
    {
      logFile << clientPrefix << " ERROR: --directory is required\n";
      return 2;
    }

    fileDir = vm.count("directory") ? vm["directory"].as<std::string>() : "";
    configPath = vm.count("config") ? vm["config"].as<std::string>() : "";

    // Read from configuration (assert config is available)
    inipp::Ini<char> ini;
    std::ifstream configFile(configPath);

    // Determine if the configuration file exists and can be opened
    if (!configFile)
    {
      logFile << clientPrefix << " ERROR: Could not open configuration file: " << configPath << "\n";
      return 1;
    }

    // Extract sections from the config (consumer-configuration)
    ini.parse(configFile);
    auto &general = ini.sections["general"];
    auto &consumer = ini.sections["consumer"];
    auto &pipeline = ini.sections["pipeline"];
    auto &aimd = ini.sections["aimd"];
    auto &cubic = ini.sections["cubic"];
    auto &producer = ini.sections["producer"];

    // Extract options from each section
    // general options
    nameConv = general["naming-convention"];
    consumerOptions.isQuiet = get_bool(general["quiet"], clientPrefix, logFile, "quiet");
    consumerOptions.isVerbose = get_bool(general["verbose"], clientPrefix, logFile, "verbose");
    asyncConsumerOptions.cwndLoggingEnabled = get_bool(general["log-cwnd"], clientPrefix, logFile, "log-cwnd");
    asyncConsumerOptions.rttLoggingEnabled = get_bool(general["log-rtt"], clientPrefix, logFile, "log-rtt");
    producerOptions.isQuiet = consumerOptions.isQuiet;
    producerOptions.isVerbose = consumerOptions.isVerbose;

    // consumer options
    consumerOptions.mustBeFresh = get_bool(consumer["fresh"], clientPrefix, logFile, "fresh");
    consumerOptions.interestLifetime = time::milliseconds(get_long(consumer["lifetime"], clientPrefix, logFile, "lifetime"));
    consumerOptions.maxRetriesOnTimeoutOrNack = get_int(consumer["retries"], clientPrefix, logFile, "retries");
    consumerOptions.disableVersionDiscovery = get_bool(consumer["no-version-discovery"], clientPrefix, logFile, "no-version-discovery");
    asyncConsumerOptions.isSaveFile = get_bool(consumer["save-to-dir"], clientPrefix, logFile, "save-to-dir");

    // producer options
    producerOptions.freshnessPeriod = time::milliseconds(get_long(producer["freshness"], clientPrefix, logFile, "freshness"));
    producerOptions.maxSegmentSize = get_int(producer["segment-size"], clientPrefix, logFile, "segment-size");
    signingInfo = producer["signing-info"];

    // pipeline options
    pipelineType = pipeline["pipeline-type"];
    consumerOptions.maxPipelineSize = get_int(pipeline["pipeline-size"], clientPrefix, logFile, "pipeline-size");
    consumerOptions.ignoreCongMarks = get_bool(pipeline["ignore-marks"], clientPrefix, logFile, "ignore-marks");
    consumerOptions.disableCwa = get_bool(pipeline["disable-cwa"], clientPrefix, logFile, "disable-cwa");
    consumerOptions.initCwnd = get_double(pipeline["init-cwnd"], clientPrefix, logFile, "init-cwnd");
    consumerOptions.initSsthresh = get_double(pipeline["init-ssthresh"], clientPrefix, logFile, "init-ssthresh");
    rttEstOptions.alpha = get_double(pipeline["rto-alpha"], clientPrefix, logFile, "rto-alpha");
    rttEstOptions.beta = get_double(pipeline["rto-beta"], clientPrefix, logFile, "rto-beta");
    rttEstOptions.k = get_int(pipeline["rto-k"], clientPrefix, logFile, "rto-k");
    rttEstOptions.minRto = time::milliseconds(get_long(pipeline["min-rto"], clientPrefix, logFile, "min-rto"));
    rttEstOptions.maxRto = time::milliseconds(get_long(pipeline["max-rto"], clientPrefix, logFile, "max-rto"));
    consumerOptions.rtoCheckInterval = time::milliseconds(get_long(pipeline["rto-check-interval"], clientPrefix, logFile, "rto-check-interval"));
    rttEstOptions.initialRto = time::milliseconds(get_long(pipeline["initial-rto"], clientPrefix, logFile, "initial-rto"));
    rttEstOptions.rtoBackoffMultiplier = get_double(pipeline["rto-backoff-multiplier"], clientPrefix, logFile, "rto-backoff-multiplier");

    // aimd options
    consumerOptions.aiStep = get_double(aimd["aimd-step"], clientPrefix, logFile, "aimd-step");
    consumerOptions.mdCoef = get_double(aimd["aimd-beta"], clientPrefix, logFile, "aimd-beta");
    consumerOptions.resetCwndToInit = get_bool(aimd["reset-cwnd-to-init"], clientPrefix, logFile, "reset-cwnd-to-init");

    // cubic options
    consumerOptions.cubicBeta = get_double(cubic["cubic-beta"], clientPrefix, logFile, "cubic-beta");
    consumerOptions.enableFastConv = get_bool(cubic["fast-conv"], clientPrefix, logFile, "fast-conv");

    // checking configured options
    if (nameConv == "marker" || nameConv == "m" || nameConv == "1")
    {
      name::setConventionEncoding(name::Convention::MARKER);
    }
    else if (nameConv == "typed" || nameConv == "t" || nameConv == "2")
    {
      name::setConventionEncoding(name::Convention::TYPED);
    }
    else if (!nameConv.empty())
    {
      logFile << clientPrefix << " ERROR: '" << nameConv << "' is not a valid naming convention\n";
      return 2;
    }

    // checking consumer options
    if (consumerOptions.interestLifetime < 0_ms)
    {
      logFile << clientPrefix << " ERROR: --lifetime cannot be negative\n";
      return 2;
    }

    if (consumerOptions.maxRetriesOnTimeoutOrNack < -1 || consumerOptions.maxRetriesOnTimeoutOrNack > 1024)
    {
      logFile << clientPrefix << " ERROR: --retries must be between -1 and 1024\n";
      return 2;
    }

    if (consumerOptions.isQuiet && consumerOptions.isVerbose)
    {
      logFile << clientPrefix << " ERROR: consumer and producer cannot be quiet and verbose at the same time\n";
      return 2;
    }

    if (consumerOptions.maxPipelineSize < 1 || consumerOptions.maxPipelineSize > 1024)
    {
      logFile << clientPrefix << " ERROR: --pipeline-size must be between 1 and 1024\n";
      return 2;
    }

    if (rttEstOptions.k < 0)
    {
      logFile << clientPrefix << " ERROR: --rto-k cannot be negative\n";
      return 2;
    }

    if (rttEstOptions.minRto < 0_ms)
    {
      logFile << clientPrefix << " ERROR: --min-rto cannot be negative\n";
      return 2;
    }

    if (rttEstOptions.maxRto < rttEstOptions.minRto)
    {
      logFile << clientPrefix << " ERROR: --max-rto cannot be smaller than --min-rto\n";
      return 2;
    }

    // checking producer options
    if (producerOptions.freshnessPeriod < 0_ms)
    {
      logFile << clientPrefix << " ERROR: --freshness cannot be negative\n";
      return 2;
    }

    if (producerOptions.maxSegmentSize < 1 || producerOptions.maxSegmentSize > MAX_NDN_PACKET_SIZE)
    {
      logFile << clientPrefix << " ERROR: --size must be between 1 and " << MAX_NDN_PACKET_SIZE << "\n";
      return 2;
    }

    try
    {
      producerOptions.signingInfo = security::SigningInfo(signingInfo);
    }
    catch (const std::invalid_argument &e)
    {
      logFile << clientPrefix << " ERROR: " << e.what() << "\n";
      return 2;
    }

    // setting AsyncConsumerOptions
    asyncConsumerOptions.fileDir = fileDir;
    asyncConsumerOptions.fileName = fileName;
    asyncConsumerOptions.pipelineType = pipelineType;
    asyncConsumerOptions.signalFile = signalFile;

    // remove the signal file if it exists
    std::string m_signal = "/tmp/ndn/" + std::to_string(id) + ".ok";
    std::remove(signalFile.c_str()); // rm /tmp/ndn/all.ok
    std::remove(m_signal.c_str());   // rm /tmp/ndn/<id>.ok

    // main logic
    try
    {
      std::unique_ptr<ndn::chunks::AsyncProducer> asyncProducer;
      std::vector<std::unique_ptr<AsyncConsumer>> asyncConsumers;

      // Create the async producer and consumers
      asyncProducer = std::make_unique<ndn::chunks::AsyncProducer>(id, fileDir, producerOptions);
      for (int targetProducer = 0; targetProducer < totalNodes; ++targetProducer)
      {
        if (targetProducer == id)
        {
          continue; // Skip self
        }
        asyncConsumers.push_back(std::make_unique<AsyncConsumer>(id, targetProducer, asyncConsumerOptions, consumerOptions, rttEstOptions));
      }

      // Start the async producer
      asyncProducer->start();

      // Start the async consumers
      for (auto &consumer : asyncConsumers)
      {
        consumer->start();
      }

      // Wait for the async consumers to finish
      logFile << clientPrefix << " Waiting for all consumers to complete..." << std::endl;

      int successCount = 0;
      int failureCount = 0;

      for (auto &consumer : asyncConsumers)
      {
        consumer->join(); // 等待该Consumer完成
        int exitCode = consumer->getExitCode();

        if (exitCode == 0)
        {
          successCount++;
        }
        else
        {
          failureCount++;
          logFile << clientPrefix << " Consumer failed with exit code: " << exitCode << std::endl;
        }
      }

      logFile << clientPrefix << " SUMMARY: Success=" << successCount
              << ", Failed=" << failureCount
              << ", Total=" << (successCount + failureCount) << std::endl;
      
      asyncProducer->join(); // 等待Producer完成
      return 0;
    }
    catch (const std::exception &e)
    {
      logFile << clientPrefix << " ERROR: " << e.what() << "\n";
      return 1;
    }
  }

  // helper functions
  static bool get_bool(std::string const &value, std::string const &clientPrefix, std::ofstream &os, std::string const &errorMsg)
  {
    if (value == "true")
    {
      return true;
    }
    else if (value == "false")
    {
      return false;
    }
    else
    {
      os << clientPrefix << " ERROR: Invalid boolean value from consumer option " << errorMsg << ": " << value << ", only allows true/false\n";
      exit(1);
    }
  }

  static long get_long(std::string const &value, std::string const &clientPrefix, std::ofstream &os, std::string const &errorMsg)
  {
    if (value == "max")
    {
      return std::numeric_limits<long>::max();
    }
    try
    {
      return std::stol(value);
    }
    catch (const std::invalid_argument &)
    {
      os << clientPrefix << " ERROR: Invalid long value from consumer option " << errorMsg << ": " << value << "\n";
      exit(1);
    }
  }

  static int get_int(std::string const &value, std::string const &clientPrefix, std::ofstream &os, std::string const &errorMsg)
  {
    if (value == "max")
    {
      return std::numeric_limits<int>::max();
    }
    try
    {
      return std::stoi(value);
    }
    catch (const std::invalid_argument &)
    {
      os << clientPrefix << " ERROR: Invalid integer value from consumer option " << errorMsg << ": " << value << "\n";
      exit(1);
    }
  }

  static double get_double(std::string const &value, std::string const &clientPrefix, std::ofstream &os, std::string const &errorMsg)
  {
    if (value == "max")
    {
      return std::numeric_limits<double>::max();
    }
    try
    {
      return std::stod(value);
    }
    catch (const std::invalid_argument &)
    {
      os << clientPrefix << " ERROR: Invalid double value from consumer option " << errorMsg << ": " << value << "\n";
      return 0.0; // Return default value on error
    }
  }

} // namespace ndn::get

int main(int argc, char *argv[])
{
  return ndn::get::main(argc, argv);
}
