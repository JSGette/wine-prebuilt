#include <windows.h>

#include <cstdio>
#include <cwchar>
#include <string>
#include <vector>

#if defined(__aarch64__)
constexpr char kArchitecture[] = "arm64";
#elif defined(__x86_64__)
constexpr char kArchitecture[] = "amd64";
#elif defined(__i386__)
constexpr char kArchitecture[] = "i386";
#else
#error Unsupported Windows payload architecture
#endif

DWORD WINAPI Thread(void*) { return 37; }

int Fail(const char* operation) {
  std::fprintf(stderr, "%s failed: %lu\n", operation, GetLastError());
  return 1;
}

int wmain(int argc, wchar_t** argv) {
  if (argc == 2 && std::wcscmp(argv[1], L"--child") == 0) {
    std::printf("child=%s\n", kArchitecture);
    return 0;
  }
  if (argc == 3 && std::wcscmp(argv[1], L"--exit") == 0) {
    return static_cast<int>(std::wcstol(argv[2], nullptr, 10));
  }
  if (argc != 8 || std::wcscmp(argv[1], L"--exercise") != 0) {
    std::fprintf(stderr,
                 "Expected --exercise DLL CHILD OUTPUT SPACE UNICODE EMPTY\n");
    return 2;
  }
  if (std::wcscmp(argv[5], L"argument with spaces") != 0 ||
      std::wcscmp(argv[6], L"caf\u00e9") != 0 || argv[7][0] != L'\0') {
    std::fprintf(stderr, "Argument round trip failed\n");
    return 3;
  }
  HMODULE library = LoadLibraryW(argv[2]);
  if (!library) return Fail("LoadLibraryW");
  auto value =
      reinterpret_cast<int (*)()>(GetProcAddress(library, "payload_value"));
  if (!value || value() != 42) return Fail("DLL export");
  FreeLibrary(library);

  HANDLE thread = CreateThread(nullptr, 0, Thread, nullptr, 0, nullptr);
  if (!thread) return Fail("CreateThread");
  DWORD thread_exit = 0;
  if (WaitForSingleObject(thread, 10000) != WAIT_OBJECT_0 ||
      !GetExitCodeThread(thread, &thread_exit) || thread_exit != 37) {
    return Fail("thread completion");
  }
  CloseHandle(thread);

  std::wstring command = L"\"" + std::wstring(argv[3]) + L"\" --child";
  std::vector<wchar_t> writable(command.begin(), command.end());
  writable.push_back(L'\0');
  STARTUPINFOW startup{};
  startup.cb = sizeof(startup);
  PROCESS_INFORMATION child{};
  if (!CreateProcessW(argv[3], writable.data(), nullptr, nullptr, TRUE, 0,
                      nullptr, nullptr, &startup, &child)) {
    return Fail("CreateProcessW");
  }
  DWORD child_exit = 0;
  if (WaitForSingleObject(child.hProcess, 30000) != WAIT_OBJECT_0 ||
      !GetExitCodeProcess(child.hProcess, &child_exit) || child_exit != 0) {
    TerminateProcess(child.hProcess, 1);
    return Fail("child completion");
  }
  CloseHandle(child.hThread);
  CloseHandle(child.hProcess);

  HANDLE output = CreateFileW(argv[4], GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS,
                              FILE_ATTRIBUTE_NORMAL, nullptr);
  if (output == INVALID_HANDLE_VALUE) return Fail("CreateFileW");
  constexpr char contents[] = "wine-prebuilt: args, DLL, threads, child OK\n";
  DWORD written = 0;
  if (!WriteFile(output, contents, sizeof(contents) - 1, &written, nullptr) ||
      written != sizeof(contents) - 1) {
    return Fail("WriteFile");
  }
  CloseHandle(output);
  std::printf("payload=%s\n", kArchitecture);
  return 0;
}
