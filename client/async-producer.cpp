#include "async-producer.hpp"

namespace ndn::chunks
{
    class AsyncProducer
    {
    private:
        int producerId;
        const std::string& fileDir;
        std::thread producerThread;
        std::atomic<int> exitCode{-1};
        std::string prefix; // producer0

        const ndn::chunks::Producer::Options& options;

    public:
        AsyncProducer(int producerId, const std::string& fileDir, const ndn::chunks::Producer::Options& options)
            : producerId(producerId), fileDir(fileDir), options(options)
        {
            prefix = "producer" + std::to_string(producerId);
        }

        void start() {
            producerThread = std::thread([this]()
                                         { this->exitCode.store(this->runProducerMain()); });
        }

        void join() {
            if (producerThread.joinable()) {
                producerThread.join();
            }
        }

        int getExitCode() const {
            return exitCode.load();
        }

        bool isFinished() const {
            return exitCode.load() != -1;
        }

    private:
        int runProducerMain() {
            std::string logFilePath = "/tmp/ndn/" + prefix + ".log";
            std::ofstream logFile(logFilePath);
            try {
                std::string socketPath = "unix:///run/nfd/" + prefix + ".sock";
                auto transport = ndn::UnixTransport::create(socketPath);
                Face face(transport);
                KeyChain keyChain;
                Producer producer(prefix, face, keyChain, options, fileDir);
                
                sendConsumerSignal();
                if (options.isVerbose) {
                    logFile << prefix << " is ready! \n";
                } 

                producer.run();
                return 0;

            } catch (const std::exception &e) {
                logFile << prefix << " ERROR: " << e.what() << "\n";
                return 1;
            }
            return 0;
        }

        void sendConsumerSignal() {
            std::filesystem::create_directories("/tmp/ndn");
            std::string signalFilePath = "/tmp/ndn/" + prefix + ".ok";
            std::ofstream signalFile(signalFilePath);
            if (signalFile.is_open()) {
                signalFile << prefix << " is ready!";
                signalFile.close();
            } else {
                throw std::runtime_error("Failed to create signal file: " + signalFilePath);
            }
        }
    }; // class AsyncProducer
} // namespace ndn::chunks

#endif // CLIENT_ASYNC_PRODUCER_HPP