#ifndef CLIENT_ASYNC_CONSUMER_HPP
#define CLIENT_ASYNC_CONSUMER_HPP

#include "consumer.hpp"
#include "discover-version.hpp"
#include "pipeline-interests-aimd.hpp"
#include "pipeline-interests-cubic.hpp"
#include "pipeline-interests-fixed.hpp"
#include "statistics-collector.hpp"
#include "core/version.hpp"

#include <ndn-cxx/security/validator-null.hpp>
#include <ndn-cxx/util/rtt-estimator.hpp>
#include <thread>
#include <spdlog/spdlog.h>
#include <spdlog/sinks/basic_file_sink.h>
#include <ndn-cxx/transport/unix-transport.hpp>
#include <atomic>
#include <fstream>

namespace ndn::get
{
    struct AsyncConsumerOptions{
        bool isSaveFile = true;          // determine whether to save the file
        bool cwndLoggingEnabled = true;  // determine whether to enable congestion window logging
        bool rttLoggingEnabled = true;   // determine whether to enable RTT logging
        std::string fileName;     // fileName is the file to request
        std::string fileDir;      // determine where to save the file
        std::string pipelineType; // type of the pipeline to use (fixed, aimd, cubic)
        std::string signalFile = "/tmp/ndn/ok"; // signal file
    };


    class AsyncConsumer
    {
    private:
        int consumerId, producerId;
        std::thread consumerThread;
        std::atomic<int> exitCode{-1};
        std::string prefix; // consumer0-1

        const AsyncConsumerOptions& asyncOptions;
        const Options& options;
        const util::RttEstimator::Options rttEstOptions;
        
        const std::chrono::duration<int64_t, std::nano> waitTimeout{30}; // default wait timeout in seconds
  
        public:
        AsyncConsumer(int consumerId, int producerId, const AsyncConsumerOptions &asyncOptions, const Options &options, const util::RttEstimator::Options &rttEstOptions);
        
        AsyncConsumer(const AsyncConsumer&) = delete;
        AsyncConsumer& operator=(const AsyncConsumer&) = delete;

        void start();

        void join();

        int getExitCode() const;

        bool isFinished() const;

    private:
        int runConsumerMain();

        void waitForProducer(std::ofstream &logFile);

    }; // class AsyncConsumer
} // namespace ndn::get

#endif // CLIENT_ASYNC_CONSUMER_HPP