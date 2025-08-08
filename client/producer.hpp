/*
This file is based on the part of ndn-tools chunks
*/
#ifndef IMAgg_Producer_HPP
#define IMAgg_Producer_HPP

#include <ndn-cxx/face.hpp>
#include <ndn-cxx/security/key-chain.hpp>
#include <fstream>

#ifdef UNIT_TEST
#define PUBLIC_WITH_TESTS_ELSE_PRIVATE public
#else
#define PUBLIC_WITH_TESTS_ELSE_PRIVATE private
#endif

namespace ndn::chunks
{
    class Producer : noncopyable
    {
    public:
        struct Options
        {
            security::SigningInfo signingInfo;
            time::milliseconds freshnessPeriod;
            size_t maxSegmentSize;
            bool isQuiet;
            bool isVerbose;
        };

        /**
         * @brief Create the producer.
         * @param prefix prefix used to publish data; if the last component is not a valid
         *               version number, the current system time is used as version number.
         */
        Producer(const Name &prefix, Face &face, KeyChain &keyChain,
                 const Options &opts, std::string fileDir);

        /**
         * @brief Run the producer.
         */
        void
        run();

        /**
         * @brief Segment the input stream and store the segments.
         * @param chunknumber the chunk number of the input stream
         * @param interest the Interest packet
         */
        void
        segmentationFile(const Interest &interest);

    private:
        /**
         * @brief Respond with the requested segment of content.
         */
        void
        processSegmentInterest(const Interest &interest);

        /**
         * @brief Get the agg tree structure
         */
        void
        processInitializaionInterest(const Interest &interest);
        PUBLIC_WITH_TESTS_ELSE_PRIVATE : std::unordered_map<std::string, std::vector<std::shared_ptr<Data>>> m_store;

    private:
        Name m_prefix;
        Face &m_face;
        KeyChain &m_keyChain;
        const Options m_options;
        std::unordered_map<std::string, uint64_t> m_nSentSegments;
        bool isini = false;
        std::string m_fileDir;
    };
} // namespace ndn::chunks

#endif // IMAgg_Producer_HPP