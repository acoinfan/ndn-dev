#ifndef NDN_TOOLS_CORE_COMMON_HPP
#define NDN_TOOLS_CORE_COMMON_HPP

#include <ndn-cxx/face.hpp>
#include <ndn-cxx/name.hpp>
#include <ndn-cxx/data.hpp>
#include <ndn-cxx/interest.hpp>
#include <ndn-cxx/util/time.hpp>
#include <ndn-cxx/util/signal.hpp>

using namespace ndn;
using namespace ndn::time;

// Compatibility macros for older ndn-cxx versions
#ifndef NDN_CXX_PUBLIC_WITH_TESTS_ELSE_PROTECTED
#define PUBLIC_WITH_TESTS_ELSE_PROTECTED protected
#else
#define PUBLIC_WITH_TESTS_ELSE_PROTECTED NDN_CXX_PUBLIC_WITH_TESTS_ELSE_PROTECTED
#endif

#ifndef NDN_CXX_PUBLIC_WITH_TESTS_ELSE_PRIVATE
#define PUBLIC_WITH_TESTS_ELSE_PRIVATE private
#else
#define PUBLIC_WITH_TESTS_ELSE_PRIVATE NDN_CXX_PUBLIC_WITH_TESTS_ELSE_PRIVATE
#endif

// Utility macro for forwarding to member function
#define FORWARD_TO_MEM_FN(func) \
  [this] (auto&&... args) { \
    return this->func(std::forward<decltype(args)>(args)...); \
  }

// Utility function to get segment number from packet
inline uint64_t
getSegmentFromPacket(const Data& data)
{
  const Name& name = data.getName();
  if (name.empty()) {
    return 0;
  }
  
  const name::Component& lastComponent = name.at(-1);
  if (lastComponent.isSegment()) {
    return lastComponent.toSegment();
  }
  
  return 0;
}

#endif // NDN_TOOLS_CORE_COMMON_HPP
