#ifndef CLIENT_ASYNC_PRODUCER_HPP
#define CLIENT_ASYNC_PRODUCER_HPP

#include "producer.hpp"
#include "core/version.hpp"

#include <ndn-cxx/security/validator-null.hpp>
#include <ndn-cxx/util/rtt-estimator.hpp>
#include <thread>

#include <ndn-cxx/transport/unix-transport.hpp>
#include <atomic>
#include <fstream>
#include <filesystem>

namespace ndn::serve
{
    class AsyncProducer
    {
    private:
        int producerId;
        const std::string& fileDir;
        std::thread producerThread;
        std::atomic<int> exitCode{-1};
        std::string prefix; // producer0

        const ndn::serve::Producer::Options& options;

    public:
        AsyncProducer(int producerId, const std::string& fileDir, const ndn::serve::Producer::Options& options);

        void start();

        void join();

        int getExitCode() const;

        bool isFinished() const;

    private:
        int runProducerMain();

        void sendConsumerSignal();
    }; // class AsyncProducer
} // namespace ndn::chunks

#endif // CLIENT_ASYNC_PRODUCER_HPP