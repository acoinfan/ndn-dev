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

#include "consumer.hpp"
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

#include "producer.hpp"
#include "inipp.h"

namespace ndn::get {

namespace po = boost::program_options;

// declaration of helper functions
static bool get_bool(std::string const& value, std::string const& errorMsg = "");

static int get_int(std::string const& value, std::string const& errorMsg = "");

static double get_double(std::string const& value, std::string const& errorMsg = "");

static long get_long(std::string const& value, std::string const& errorMsg = "");
// end of declaration

static int main(int argc, char* argv[])
{
  // Initialize options and variables
  Options consumerOptions;
  ndn::chunks::Producer::Options producerOptions;

  std::string fileName, nameConv, pipelineType, configPath, fileDir, signingInfo; // fileName is the file to be fetched and sent
  int id, totalNodes;
  std::string cwndPath, rttPath;
  util::RttEstimator::Options rttEstOptions;
  const std::string programName(argv[0]);
  
  // Analyse command line options
  po::options_description basicDesc("Basic Options");
  basicDesc.add_options()
    ("help,h",      "print this help message and exit")
    ("config,c", po::value<std::string>(&configPath),
                    "path to the configuration file")
    ("filename,f",  po::value<std::string>(&fileName),
                    "file name of the requested content")
    ("id,i",        po::value<int>(&id),
                    "the unique ID of this consumer node")
    ("nodes,n",     po::value<int>(&totalNodes),
                    "the total number of consumer nodes in the experiment")
    ("directory,d", po::value<std::string>(&fileDir)->required(), "Directory of files to store and send (absolute path)");
  
  po::variables_map vm;
  po::store(po::command_line_parser(argc, argv).options(basicDesc).run(), vm);
  po::notify(vm);

  if (vm.count("help") > 0) {
    std::cout << "Usage: " << programName << " [options]\n";
    std::cout << basicDesc;
    return 0;
  }

  if (vm.count("config") == 0) {
    std::cerr << "ERROR: --config is required\n";
    return 2;
  }

  if (vm.count("filename") == 0) {
    std::cerr << "ERROR: --filename is required\n";
    return 2;
  }

  if (vm.count("id") == 0) {
    std::cerr << "ERROR: --id is required\n";
    return 2;
  }

  if (vm.count("nodes") == 0) {
    std::cerr << "ERROR: --nodes is required\n";
    return 2;
  }

  if (vm.count("directory") == 0) {
    std::cerr << "ERROR: --directory is required\n";
    return 2;
  }

  fileDir = vm.count("directory") ? vm["directory"].as<std::string>() : "";
  configPath = vm.count("conconfig") ? vm["conconfig"].as<std::string>() : "";


  // Read from configuration (assert config is available)
  inipp::Ini<char> ini;
  std::ifstream configFile(configPath);

  // Determine if the configuration file exists and can be opened
  if (!configFile) {
    std::cerr << "ERROR: Could not open configuration file: " << configPath << "\n";
    return 1;
  }


  // Extract sections from the config (consumer-configuration)
  ini.parse(configFile);
  auto& consumer = ini.sections["consumer"];
  auto& pipeline = ini.sections["pipeline"];
  auto& aimd = ini.sections["aimd"];
  auto& cubic = ini.sections["cubic"];
  auto& producer = ini.sections["producer"];

  // Extract options from each section
  // consumer options
  consumerOptions.mustBeFresh = get_bool(consumer["fresh"], "fresh");
  consumerOptions.interestLifetime = time::milliseconds(get_long(consumer["lifetime"], "lifetime"));
  consumerOptions.maxRetriesOnTimeoutOrNack = get_int(consumer["retries"], "retries");
  consumerOptions.disableVersionDiscovery = get_bool(consumer["no-version-discovery"], "no-version-discovery");
  nameConv = consumer["naming-convention"];
  consumerOptions.isQuiet = get_bool(consumer["quiet"], "quiet");
  consumerOptions.isVerbose = get_bool(consumer["verbose"], "verbose");

  // pipeline options
  pipelineType = pipeline["pipeline-type"];
  consumerOptions.maxPipelineSize = get_int(pipeline["pipeline-size"], "pipeline-size");
  consumerOptions.ignoreCongMarks = get_bool(pipeline["ignore-marks"], "ignore-marks");
  consumerOptions.disableCwa = get_bool(pipeline["disable-cwa"], "disable-cwa");
  consumerOptions.initCwnd = get_double(pipeline["init-cwnd"], "init-cwnd");
  consumerOptions.initSsthresh = get_double(pipeline["init-ssthresh"], "init-ssthresh");
  rttEstOptions.alpha = get_double(pipeline["rto-alpha"], "rto-alpha");
  rttEstOptions.beta = get_double(pipeline["rto-beta"], "rto-beta");
  rttEstOptions.k = get_int(pipeline["rto-k"], "rto-k");
  rttEstOptions.minRto = time::milliseconds(get_long(pipeline["min-rto"], "min-rto"));
  rttEstOptions.maxRto = time::milliseconds(get_long(pipeline["max-rto"], "max-rto"));
  cwndPath = pipeline["log-cwnd"];
  rttPath = pipeline["log-rtt"];
  consumerOptions.rtoCheckInterval = time::milliseconds(get_long(pipeline["rto-check-interval"], "rto-check-interval"));
  rttEstOptions.initialRto = time::milliseconds(get_long(pipeline["initial-rto"], "initial-rto"));
  rttEstOptions.rtoBackoffMultiplier = get_double(pipeline["rto-backoff-multiplier"], "rto-backoff-multiplier");

  // aimd options
  consumerOptions.aiStep = get_double(aimd["aimd-step"], "aimd-step");
  consumerOptions.mdCoef = get_double(aimd["aimd-beta"], "aimd-beta");
  consumerOptions.resetCwndToInit = get_bool(aimd["reset-cwnd-to-init"], "reset-cwnd-to-init");

  // cubic options
  consumerOptions.cubicBeta = get_double(cubic["cubic-beta"], "cubic-beta");
  consumerOptions.enableFastConv = get_bool(cubic["fast-conv"], "fast-conv");

  // producer options
  producerOptions.freshnessPeriod = time::milliseconds(get_long(producer["freshness"], "freshness"));
  producerOptions.maxSegmentSize = get_int(producer["segment-size"], "segment-size");
  signingInfo = producer["signing-info"];
  producerOptions.isQuiet = get_bool(producer["quiet"], "quiet");
  producerOptions.isVerbose = get_bool(producer["verbose"], "verbose");

  // checking configured options
  if (nameConv != producer["naming-convention"]) {
    std::cerr << "ERROR: naming convention in consumer (" << nameConv
              << ") does not match producer (" << producer["naming-convention"] << ")\n";
    return 2;
  }

  if (nameConv == "marker" || nameConv == "m" || nameConv == "1") {
    name::setConventionEncoding(name::Convention::MARKER);
  }
  else if (nameConv == "typed" || nameConv == "t" || nameConv == "2") {
    name::setConventionEncoding(name::Convention::TYPED);
  }
  else if (!nameConv.empty()) {
    std::cerr << "ERROR: '" << nameConv << "' is not a valid naming convention\n";
    return 2;
  }

  // checking consumer options
  if (consumerOptions.interestLifetime < 0_ms) {
    std::cerr << "ERROR: --lifetime cannot be negative\n";
    return 2;
  }

  if (consumerOptions.maxRetriesOnTimeoutOrNack < -1 || consumerOptions.maxRetriesOnTimeoutOrNack > 1024) {
    std::cerr << "ERROR: --retries must be between -1 and 1024\n";
    return 2;
  }

  if (consumerOptions.isQuiet && consumerOptions.isVerbose) {
    std::cerr << "ERROR: consumer cannot be quiet and verbose at the same time\n";
    return 2;
  }

  if (consumerOptions.maxPipelineSize < 1 || consumerOptions.maxPipelineSize > 1024) {
    std::cerr << "ERROR: --pipeline-size must be between 1 and 1024\n";
    return 2;
  }

  if (rttEstOptions.k < 0) {
    std::cerr << "ERROR: --rto-k cannot be negative\n";
    return 2;
  }

  if (rttEstOptions.minRto < 0_ms) {
    std::cerr << "ERROR: --min-rto cannot be negative\n";
    return 2;
  }

  if (rttEstOptions.maxRto < rttEstOptions.minRto) {
    std::cerr << "ERROR: --max-rto cannot be smaller than --min-rto\n";
    return 2;
  }

  // checking producer options
  if (producerOptions.freshnessPeriod < 0_ms)
  {
      std::cerr << "ERROR: --freshness cannot be negative\n";
      return 2;
  }

  if (producerOptions.maxSegmentSize < 1 || producerOptions.maxSegmentSize > MAX_NDN_PACKET_SIZE)
  {
      std::cerr << "ERROR: --size must be between 1 and " << MAX_NDN_PACKET_SIZE << "\n";
      return 2;
  }

  try
  {
      producerOptions.signingInfo = security::SigningInfo(signingInfo);
  }
  catch (const std::invalid_argument &e)
  {
      std::cerr << "ERROR: " << e.what() << "\n";
      return 2;
  }

  if (producerOptions.isQuiet && producerOptions.isVerbose)
  {
      std::cerr << "ERROR: producer cannot be quiet and verbose at the same time\n";
      return 2;
  }

  // main logic
  try {
    auto transport = ndn::UnixTransport::create("unix:///run/nfd/consumer1.sock");
    Face face(transport);
    auto discover = std::make_unique<DiscoverVersion>(face, Name(prefix), options);
    std::unique_ptr<PipelineInterests> pipeline;
    std::unique_ptr<StatisticsCollector> statsCollector;
    std::unique_ptr<RttEstimatorWithStats> rttEstimator;
    std::ofstream statsFileCwnd;
    std::ofstream statsFileRtt;

    // print configuration of pipeline
    if (pipelineType == "fixed") {
      pipeline = std::make_unique<PipelineInterestsFixed>(face, options);
    }
    else if (pipelineType == "aimd" || pipelineType == "cubic") {
      if (options.isVerbose) {
        using namespace ndn::time;
        std::cerr << "RTT estimator parameters:\n"
                  << "\tAlpha = " << rttEstOptions.alpha << "\n"
                  << "\tBeta = " << rttEstOptions.beta << "\n"
                  << "\tK = " << rttEstOptions.k << "\n"
                  << "\tInitial RTO = " << duration_cast<milliseconds>(rttEstOptions.initialRto) << "\n"
                  << "\tMin RTO = " << duration_cast<milliseconds>(rttEstOptions.minRto) << "\n"
                  << "\tMax RTO = " << duration_cast<milliseconds>(rttEstOptions.maxRto) << "\n"
                  << "\tBackoff multiplier = " << rttEstOptions.rtoBackoffMultiplier << "\n";
      }
      rttEstimator = std::make_unique<RttEstimatorWithStats>(std::move(rttEstOptions));

      std::unique_ptr<PipelineInterestsAdaptive> adaptivePipeline;
      if (pipelineType == "aimd") {
        adaptivePipeline = std::make_unique<PipelineInterestsAimd>(face, *rttEstimator, options);
      }
      else {
        adaptivePipeline = std::make_unique<PipelineInterestsCubic>(face, *rttEstimator, options);
      }

      if (!cwndPath.empty() || !rttPath.empty()) {
        if (!cwndPath.empty()) {
          statsFileCwnd.open(cwndPath);
          if (statsFileCwnd.fail()) {
            std::cerr << "ERROR: failed to open '" << cwndPath << "'\n";
            return 4;
          }
        }
        if (!rttPath.empty()) {
          statsFileRtt.open(rttPath);
          if (statsFileRtt.fail()) {
            std::cerr << "ERROR: failed to open '" << rttPath << "'\n";
            return 4;
          }
        }
        statsCollector = std::make_unique<StatisticsCollector>(*adaptivePipeline, statsFileCwnd, statsFileRtt);
      }

      pipeline = std::move(adaptivePipeline);
    }
    else {
      std::cerr << "ERROR: '" << pipelineType << "' is not a valid pipeline type\n";
      return 2;
    }

    std::ofstream outputStream("/dev/null");
    Consumer consumer(security::getAcceptAllValidator(), outputStream);
    BOOST_ASSERT(discover != nullptr);
    BOOST_ASSERT(pipeline != nullptr);
    consumer.run(std::move(discover), std::move(pipeline));
    face.processEvents();
  }
  catch (const Consumer::ApplicationNackError& e) {
    std::cerr << "ERROR: " << e.what() << "\n";
    return 3;
  }
  catch (const Consumer::DataValidationError& e) {
    std::cerr << "ERROR: " << e.what() << "\n";
    return 5;
  }
  catch (const std::exception& e) {
    std::cerr << "ERROR: " << e.what() << "\n";
    return 1;
  }

  return 0;
}

// helper functions
static bool get_bool(std::string const& value, std::string const& errorMsg)
{
  if (value == "true") {
    return true;
  } else if (value == "false") {
    return false;
  } else {
    std::cerr << "ERROR: Invalid boolean value from consumer option " << errorMsg << ": " << value << ", only allows true/false\n";
    exit(1);
  }
}

static long get_long(std::string const& value, std::string const& errorMsg)
{
  if (value == "max") {
    return std::numeric_limits<long>::max();
  }
  try {
    return std::stol(value);
  } catch (const std::invalid_argument&) {
    std::cerr << "ERROR: Invalid long value from consumer option " << errorMsg << ": " << value << "\n";
    exit(1); 
  }
}

static int get_int(std::string const& value, std::string const& errorMsg)
{
  if (value == "max") {
    return std::numeric_limits<int>::max();
  }
  try {
    return std::stoi(value);
  } catch (const std::invalid_argument&) {
    std::cerr << "ERROR: Invalid integer value from consumer option " << errorMsg << ": " << value << "\n";
    exit(1); 
  }
}

static double get_double(std::string const& value, std::string const& errorMsg)
{
  if (value == "max") {
    return std::numeric_limits<double>::max();
  }
  try {
    return std::stod(value);
  } catch (const std::invalid_argument&) {
    std::cerr << "ERROR: Invalid double value from consumer option " << errorMsg << ": " << value << "\n";
  }
}

} // namespace ndn::get

int
main(int argc, char* argv[])
{
  return ndn::get::main(argc, argv);
}
